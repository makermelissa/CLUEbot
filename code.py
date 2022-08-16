import time
import board
import pwmio
import neopixel
import displayio
import vectorio

import adafruit_motor.servo
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from adafruit_bluefruit_connect.packet import Packet
from adafruit_bluefruit_connect.color_packet import ColorPacket
from adafruit_bluefruit_connect.packet import Packet
from adafruit_bluefruit_connect.button_packet import ButtonPacket
from adafruit_bluefruit_connect.color_packet import ColorPacket

# Throttle Directions and Speeds
FWD = 1.0
REV = -1.0
STOP = 0

# Custom Colors
RED = (200, 0, 0)
GREEN = (0, 200, 0)
BLUE = (0, 0, 200)
PURPLE = (120, 0, 160)
YELLOW = (100, 100, 0)
AQUA = (0, 100, 100)

class Robot:
    def __init__(self, left_pin, right_pin, underlight_neopixel, status_neopixel):
        self.left_servo = self.init_motor(left_pin)
        self.right_servo = self.init_motor(right_pin)
        self.init_display()
        self.under_pixels = underlight_neopixel
        self.neopixel = status_neopixel
        self.direction = STOP
        self.ble = BLERadio()
        self.uart_service = UARTService()
        self.advertisement = ProvideServicesAdvertisement(self.uart_service)
        self.release_color = None
        self.set_underglow(PURPLE)

    @classmethod
    def init_motor(self, pin):
        pwm = pwmio.PWMOut(pin, frequency=50)
        return adafruit_motor.servo.ContinuousServo(pwm, min_pulse=600, max_pulse=2400)
    
    def init_display(self):
        self.display = board.DISPLAY
        self.display_group = displayio.Group()
        self.display.show(self.display_group)
        self.shape_color = 0
        self.bg_color = 0xFFFF00
        rect = vectorio.Rectangle(
            pixel_shader=self.make_palette(0xFFFF00),
            x=0, y=0,
            width=self.display.width,
            height=self.display.height)
        self.display_group.append(rect)

    def wait_for_connection(self):
        self.set_status_led(BLUE)
        self.ble.start_advertising(self.advertisement)
        while not self.ble.connected:
            # Wait for a connection.
            pass
        self.ble.stop_advertising()
        self.set_status_led(GREEN)
    
    def is_connected(self):
        return self.ble.connected

    def set_underglow(self, color, save_release_color = False):
        if save_release_color:
            self.release_color = self.get_underglow()
        for index, _ in enumerate(self.under_pixels):
            self.under_pixels[index] = color
    
    def get_underglow(self):
        # Set the 2 Neopixels on the underside fo the robot
        return self.under_pixels[0]

    def set_status_led(self, color):
        # Set the status NeoPixel on the CLUE
        self.neopixel[0] = color

    def set_left_throttle(self, speed):
        self.left_servo.throttle = speed

    def set_right_throttle(self, speed):
        # Motor is rotated 180 degrees of the left, so we invert the throttle
        self.right_servo.throttle = -1 * speed

    def rotate_right(self, speed):
        self.set_left_throttle(speed)
        self.set_right_throttle(-1 * speed)

    def rotate_left(self, speed):
        self.set_left_throttle(-1 * speed)
        self.set_right_throttle(speed)

    def set_throttle(self, speed):
        if speed == STOP:
            self.set_status_stop()
        self.set_left_throttle(speed)
        self.set_right_throttle(speed)

    def stop(self):
        self.set_throttle(STOP)

    def check_for_packets(self):
        if self.uart_service.in_waiting:
            self.process_packet(Packet.from_stream(self.uart_service))

    def handle_color_packet(self, packet):
        # Change the color
        self.set_underglow(packet.color)

    def remove_shapes(self):
        while len(self.display_group) > 1:
            self.display_group.pop()

    @classmethod
    def make_palette(self, color):
        palette = displayio.Palette(1)
        palette[0] = color
        return palette

    def add_centered_rect(self, width, height, x_offset=0, y_offset=0, color=None):
        if color is None:
            color = self.shape_color
        rectangle = vectorio.Rectangle(
            pixel_shader=self.make_palette(color),
            width=width,
            height=height,
            x=(self.display.width//2 - width//2) + x_offset - 1,
            y=(self.display.height//2 - height//2) + y_offset - 1
        )
        self.display_group.append(rectangle)
    
    def add_centered_polygon(self, points, x_offset=0, y_offset=0, color=None):
        if color is None:
            color = self.shape_color
        # Figure out the shape dimensions by using min and max
        width = max(points, key=lambda item:item[0])[0] - min(points, key=lambda item:item[0])[0]
        height = max(points, key=lambda item:item[1])[1] - min(points, key=lambda item:item[1])[1]
        polygon = vectorio.Polygon(
            pixel_shader=self.make_palette(color),
            points=points, 
            x=(self.display.width // 2 - width // 2) + x_offset - 1,
            y=(self.display.height // 2 - height // 2) + y_offset - 1
        )
        self.display_group.append(polygon)

    def add_centered_circle(self, radius, x_offset=0, y_offset=0, color=None):
        if color is None:
            color = self.shape_color
        circle = vectorio.Circle(
            pixel_shader=self.make_palette(color),
            radius=radius,
            x=(self.display.width // 2) + x_offset - 1,
            y=(self.display.height // 2) + y_offset - 1
        )
        self.display_group.append(circle)

    def set_status_stop(self):
        self.remove_shapes()

    def set_status_reverse(self):
        self.remove_shapes()
        self.add_centered_polygon([(40, 0), (60, 0), (100, 100), (0, 100)], 0, 0)
        self.add_centered_polygon([(0, 40), (100, 40), (50, 0)], 0, -40)

    def set_status_forward(self):
        self.remove_shapes()
        self.add_centered_polygon([(20, 0), (60, 0), (80, 100), (0, 100)])
        self.add_centered_polygon([(0, 0), (150, 0), (75, 50)], 0, 50)

    def set_status_left(self):
        self.remove_shapes()
        self.add_centered_rect(100, 40)
        self.add_centered_polygon([(50, 0), (50, 100), (0, 50)], -50, 0)

    def set_status_rotate_ccw(self):
        self.remove_shapes()
        self.add_centered_circle(80)
        self.add_centered_circle(50, 0, 0, self.bg_color)
        self.add_centered_rect(160, 60, 0, 0, self.bg_color)
        self.add_centered_polygon([(40, 0), (80, 40), (0, 40)], 60, 10)
        self.add_centered_polygon([(40, 40), (80, 0), (0, 0)], -60, -10)

    def set_status_right(self):
        self.remove_shapes()
        self.add_centered_rect(100, 40)
        self.add_centered_polygon([(0, 0), (0, 100), (50, 50)], 50)

    def set_status_rotate_cw(self):
        self.remove_shapes()
        self.add_centered_circle(80)
        self.add_centered_circle(50, 0, 0, self.bg_color)
        self.add_centered_rect(160, 60, 0, 0, self.bg_color)
        self.add_centered_polygon([(40, 0), (80, 40), (0, 40)], -60, 10)
        self.add_centered_polygon([(40, 40), (80, 0), (0, 0)], 60, -10)

    def handle_button_press_packet(self, packet):
        if packet.button == ButtonPacket.UP:  # UP button pressed
            self.set_throttle(FWD)
            self.set_status_forward()
            self.direction = FWD
        elif packet.button == ButtonPacket.DOWN:  # DOWN button
            self.set_throttle(REV)
            self.set_status_reverse()
            self.direction = REV
        elif packet.button == ButtonPacket.RIGHT:
            self.release_color = self.get_underglow()
            self.set_underglow(YELLOW, True)
            if self.direction == STOP:
                self.set_status_rotate_cw()
                self.rotate_right(FWD)
                self.rotate_left(REV)
            else:
                self.set_status_right()
                self.set_left_throttle(self.direction)
                self.set_right_throttle(STOP)
        elif packet.button == ButtonPacket.LEFT:
            self.release_color = self.get_underglow()
            self.set_underglow(YELLOW, True)
            if self.direction == STOP:
                self.set_status_rotate_ccw()
                self.rotate_left(FWD)
                self.rotate_right(REV)
            else:
                self.set_status_left()
                self.set_left_throttle(STOP)
                self.set_right_throttle(self.direction)
        elif packet.button == ButtonPacket.BUTTON_1:
            # Temporarily grab the current color
            color = self.get_underglow()
            self.set_underglow(RED)
            self.stop()
            self.direction = STOP
            time.sleep(0.5)
            self.set_underglow(color)
        elif packet.button == ButtonPacket.BUTTON_2:
            self.set_underglow(GREEN)
        elif packet.button == ButtonPacket.BUTTON_3:
            self.set_underglow(BLUE)
        elif packet.button == ButtonPacket.BUTTON_4:
            self.set_underglow(PURPLE)

    def handle_button_release_packet(self, packet):
        if self.release_color is not None:
            self.set_underglow(self.release_color)
            self.release_color = None
        if packet.button == ButtonPacket.RIGHT:
            self.set_throttle(self.direction)
        if packet.button == ButtonPacket.LEFT:
            self.set_throttle(self.direction)

    def process_packet(self, packet):
        if isinstance(packet, ColorPacket):
            self.handle_color_packet(packet)
        elif isinstance(packet, ButtonPacket) and packet.pressed:
            # do this when buttons are pressed
            self.handle_button_press_packet(packet)
        elif isinstance(packet, ButtonPacket) and not packet.pressed:
            # do this when some buttons are released
            self.handle_button_release_packet(packet)

def rgb_to_hex(rgb):
    return int('0x%02x%02x%02x' % rgb)

underlight_neopixels = neopixel.NeoPixel(board.D0, 2)
clue_neopixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
robot = Robot(board.D1, board.D2, underlight_neopixels, clue_neopixel)

while True:
    robot.wait_for_connection()
    while robot.is_connected():
        robot.check_for_packets()