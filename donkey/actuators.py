"""
actuators.py

Classes to control the motors and servos. These classes 
are wrapped in a mixer class before being used in the drive loop.

"""

import time
import sys
import threading

def map_range(x, X_min, X_max, Y_min, Y_max):
    ''' 
    Linear mapping between two ranges of values 
    '''
    X_range = X_max - X_min
    Y_range = Y_max - Y_min
    XY_ratio = X_range/Y_range

    y = ((x-X_min) / XY_ratio + Y_min) // 1

    return int(y)


    
class RasPiRobot_Controller:
    def __init__(self, driveLeft, driveRight):
        import rrb3
        rr = RRB3(9, 6)
        leftDir = 0
        rightDir = 0
        if driveLeft < 0:  # change direction if number is negative
            leftDir = 1
        if driveRight < 0:
            rightDir = 1
        rr.set_motors(abs(driveLeft), leftDir, abs(driveRight), rightDir)


        
class PCA9685_Controller:
    ''' 
    Adafruit PWM controler. 
    This is used for most RC Cars
    '''
    def __init__(self, channel, frequency=60):
        import Adafruit_PCA9685
        # Initialise the PCA9685 using the default address (0x40).
        self.pwm = Adafruit_PCA9685.PCA9685()

        self.pwm.set_pwm_freq(frequency)
        self.channel = channel

    def set_pulse(self, pulse):
        self.pwm.set_pwm(self.channel, 0, pulse) 


        
class PWMSteeringActuator:
    #max angle wheels can turn
    LEFT_ANGLE = -1 
    RIGHT_ANGLE = 1

    def __init__(self, controller=None,
                       left_pulse=290,
                       right_pulse=490):

        self.controller = controller
        self.left_pulse = left_pulse
        self.right_pulse = right_pulse


    def update(self, angle):
        #map absolute angle to angle that vehicle can implement.
        pulse = map_range(angle, 
                          self.LEFT_ANGLE, self.RIGHT_ANGLE,
                          self.left_pulse, self.right_pulse)

        self.controller.set_pulse(pulse)



class PWMThrottleActuator:

    MIN_THROTTLE = -1
    MAX_THROTTLE =  1

    def __init__(self, controller=None,
                       max_pulse=300,
                       min_pulse=490,
                       zero_pulse=350):

        #super().__init__(channel, frequency)
        self.controller = controller
        self.max_pulse = max_pulse
        self.min_pulse = min_pulse
        self.zero_pulse = zero_pulse
        self.calibrate()


    def calibrate(self):
        #Calibrate ESC (TODO: THIS DOES NOT WORK YET)
        print('center: %s' % self.zero_pulse)
        self.controller.set_pulse(self.zero_pulse)  #Set Max Throttle
        time.sleep(1)


    def update(self, throttle):
        if throttle > 0:
            pulse = map_range(throttle,
                              0, self.MAX_THROTTLE, 
                              self.zero_pulse, self.max_pulse)
        else:
            pulse = map_range(throttle,
                              self.MIN_THROTTLE, 0, 
                              self.min_pulse, self.zero_pulse)

        sys.stdout.flush()
        self.controller.set_pulse(pulse)
        return '123'



class Adafruit_Motor_Hat_Controller:
    ''' 
    Adafruit DC Motor Controller 
    For differential drive cars you need one controller for each motor.
    '''
    def __init__(self, motor_num):
        from Adafruit_MotorHAT import Adafruit_MotorHAT, Adafruit_DCMotor
        import atexit
        
        self.FORWARD = Adafruit_MotorHAT.FORWARD
        self.BACKWARD = Adafruit_MotorHAT.BACKWARD
        self.mh = Adafruit_MotorHAT(addr=0x60) 
        
        self.motor = self.mh.getMotor(motor_num)
        self.motor_num = motor_num
        
        atexit.register(self.turn_off_motors)
        self.speed = 0
        self.throttle = 0
    

    def turn_off_motors(self):
        self.mh.getMotor(self.motor_num).run(Adafruit_MotorHAT.RELEASE)

        
    def turn(self, speed):
        '''
        Update the speed of the motor where 1 is full forward and
        -1 is full backwards.
        '''
        if speed > 1 or speed < -1:
            raise ValueError( "Speed must be between 1(forward) and -1(reverse)")
        
        self.speed = speed
        self.throttle = int(map_range(abs(speed), -1, 1, -255, 255))
        
        if speed > 0:            
            self.motor.run(self.FORWARD)
        else:
            self.motor.run(self.BACKWARD)
            
        self.motor.setSpeed(self.throttle)
        
        
    def test(self, seconds=.5):
        speeds = [-.5, -1, -.5, 0, .5, 1, 0]
        for s in speeds:
            self.turn(s)
            time.sleep(seconds)
            print('speed: %s   throttle: %s' % (self.speed, self.throttle))
        print('motor #%s test complete'% self.motor_num)

class Null_Controller:
  def __init__(self):
    self.speed = 0
    self.pololu_speed = 0
    self.throttle = 0

  def turn(self,speed):
    self.speed = speed

from pololu_drv8835_rpi import motors
pololu_lock = threading.Lock()
pololu_driver = motors
       
class DRV8835_Controller:
    ''' 
    Pololu DRV8835 controller.  Drives Pololu Dual Driver controller #2753
    Note:  Depends on wiringpi which requires root privileges
    '''
    def __init__(self, motor_num):
        import atexit
        global pololu_driver
        
        # both motors, for panic stopping 
        self.MAX_FORWARD = pololu_driver.MAX_SPEED
        self.MAX_BACKWARD = -pololu_driver.MAX_SPEED
        if motor_num == 1:
                self.motor = pololu_driver.motor1
        elif motor_num == 2:
                self.motor = pololu_driver.motor2
        self.motor_num = motor_num
        
        atexit.register(self.turn_off_motors)
        self.turn_off_motors()
        self.speed = 0
        self.throttle = 0
    

    def turn_off_motors(self):
        with pololu_lock:
          pololu_driver.setSpeeds(0,0)
        
    def turn(self, speed):
        '''
        Update the speed of the motor where 1 is full forward and
        -1 is full backwards.
        '''
        if speed > 1 or speed < -1:
            raise ValueError( "Speed must be between 1(forward) and -1(reverse)")
        self.speed = speed

        # Pololu drivers use a range of -480 => 480 for reverse and forward.
	# Multiply the input speed by MAX_SPEED to map the input value
	# to the number Pololu expects
        self.pololu_speed = int(self.speed * self.MAX_FORWARD)

        with pololu_lock:
           self.motor.setSpeed( self.pololu_speed )
           #time.sleep(0.05)
        
    def test(self, seconds=.5):
        speeds = [-.5, -1, -.5, 0, .5, 1, 0]
        for s in speeds:
            self.turn(s)
            time.sleep(seconds)
            print('speed: %s   throttle: %s' % (self.speed, self.throttle))
        print('motor #%s test complete'% self.motor_num)
 
