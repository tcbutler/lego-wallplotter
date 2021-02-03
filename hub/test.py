import math

import hub


def clamp(value, min_value, max_value):
    return min(max(round(value), min_value), max_value)


class Geom:
    """
    Calculates motor positions for coordinates
    Needs
        distance d between two anchors
        an offset of x and y where (0,0) should be relative to the left anchor
        the width and height in mm of the canvas
        how many degrees to we need per mm of rope
    """

    def __init__(self, d, offset_x, offset_y, width, height, degree_per_mm):
        self.d = d
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.width = width
        self.height = height
        self.degree_per_mm = degree_per_mm

    def get_degree(self, point):
        x = point[0]
        y = point[1]
        l = math.sqrt(
            (x * self.width + self.offset_x) ** 2 + (y * self.height + self.offset_y) ** 2) * self.degree_per_mm
        r = math.sqrt((self.d - self.offset_x - x * self.width) ** 2 + (
                y * self.height + self.offset_y) ** 2) * self.degree_per_mm
        return [l, r]


class MotorController:
    POWER_PER_DEGREE_PER_SECOND = 1 / 9.3

    def __init__(self, port_left, port_right):
        self.port_left = port_left
        self.port_right = port_right
        self.start_pos_left = 0
        self.start_pos_right = 0
        self.port_left.motor.mode([(1, 0), (2, 2), (3, 1), (0, 0)])
        self.port_right.motor.mode([(1, 0), (2, 2), (3, 1), (0, 0)])

    def preset(self):
        [self.start_pos_left, self.start_pos_right] = self.get_pos()

    def get_pos(self):
        return [self.port_left.motor.get()[1] - self.start_pos_left,
                self.port_right.motor.get()[1] - self.start_pos_right]

    def set_degree_per_second(self, left, right):
        self.port_left.pwm(round(left * self.POWER_PER_DEGREE_PER_SECOND))
        self.port_right.pwm(round(right * self.POWER_PER_DEGREE_PER_SECOND))


class PathController:
    min_steps_per_mm = 1

    def __init__(self, width_mm, height_mm):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.interpolated = []
        self.idx = 0

    def load_path(self, path):
        self.interpolated = [path[0]]
        self.idx = 0

        for p1 in path[1:]:
            p0 = self.interpolated[-1]
            dx = (p1[0] - p0[0])
            dy = (p1[1] - p0[1])
            d = math.sqrt((dx * self.width_mm) ** 2 + (dy * self.height_mm) ** 2)
            needed_points_for_distance = math.ceil(d * self.min_steps_per_mm)
            for j in range(1, needed_points_for_distance + 1):
                self.interpolated.append([p0[0] + dx * j / needed_points_for_distance,
                                          p0[1] + dy * j / needed_points_for_distance])

    def current_point(self):
        return self.interpolated[self.idx]

    def has_next(self):
        return self.idx < len(self.interpolated) - 1

    def next(self):
        self.idx += 1


class Plotter:
    mm_per_degree = -0.025
    max_deg_per_s = 930 * 0.9  # use only 90% of motors maximum speed
    width_mm = 270
    height_mm = 400

    def __init__(self):
        self.mc = MotorController(hub.port.B, hub.port.F)
        self.geom = Geom(790, 290, 640, self.width_mm, self.height_mm, (1 / self.mm_per_degree))
        self.pc = PathController(self.width_mm, self.height_mm)

    def draw(self, path):
        self.pc.load_path(path)
        self.mc.preset()
        # assume we start at (0,0) on our canvas. Canvas (0,0) is relative to left anchor at (offset_x, offset_y)
        p0 = self.geom.get_degree([0, 0])

        run = True

        for p in path:
            print(self.geom.get_degree(p))
            self.pc.next()

        while run:
            point = self.pc.current_point()
            [left_desired_deg, right_desired_deg] = self.geom.get_degree(point)
            [left_pos, right_pos] = self.mc.get_pos()

            left_error_deg = left_desired_deg - (left_pos + p0[0])
            right_error_deg = right_desired_deg - (right_pos + p0[1])

            if min(abs(left_error_deg), abs(right_error_deg)) < 5:
                # consider point reached
                if self.pc.has_next():
                    self.pc.next()
                    # print("Next point", self.pc.current_point())
                    continue
                else:
                    run = False
                    continue

            if abs(left_error_deg) > abs(right_error_deg):
                left_deg_per_s = math.copysign(self.max_deg_per_s, left_error_deg)
                right_deg_per_s = right_error_deg / abs(left_error_deg) * self.max_deg_per_s
            else:
                right_deg_per_s = math.copysign(self.max_deg_per_s, right_error_deg)
                left_deg_per_s = left_error_deg / abs(right_error_deg) * self.max_deg_per_s

            # self.mc.set_degree_per_second(0, 0)
            # print("Desired", self.geom.get_degree(point), "p0", p0, "current", self.mc.get_pos())
            # print("Point", point, "left error", left_error_deg, "right error", right_error_deg)
            # print("Power", left_deg_per_s, right_deg_per_s)

            self.mc.set_degree_per_second(left_deg_per_s, right_deg_per_s)
            # time.sleep_ms(100)

        # finished drawing, stop
        self.mc.set_degree_per_second(0, 0)


path = [
    [0, 0],
    [1, 0],
    [0, 1],
    [1, 1],
    [0, 0]
]

plotter = Plotter()
plotter.draw(path)

# lastTime = time.ticks_ms()
# lastPos = hub.port.E.motor.get()[1]
# nextPrint = lastTime + 1000
#
# pid = PID(0.00098, 0.002, 0)
# last_ticks_us = time.ticks_us()
#
# last_abs_pos = hub.port.E.motor.get()[1]
# pwm = 0
# rolling_avg = 0
# while True:
#
#     ticks_us = time.ticks_us()
#     dt = time.ticks_diff(ticks_us, last_ticks_us) * 0.000001
#     last_ticks_us = ticks_us
#
#     setpoint_dps = 500
#
#     abs_pos = hub.port.E.motor.get()[1]
#     dps = hub.port.E.motor.get()[0] * 9.3
#     last_abs_pos = abs_pos
#
#     if rolling_avg == 0:
#         rolling_avg = dps
#     rolling_avg = rolling_avg * 0.99 + 0.01 * dps
#
#     feedback = pid.process(setpoint_dps, dps, dt)
#     pwm += feedback
#     hub.port.E.motor.pwm(clamp(pwm + feedback, -100, 100))
#     # hub.port.E.motor.run_at_speed(round(setpoint_dps / 9.3))
#
#     if (time.ticks_ms() > nextPrint):
#         now = time.ticks_ms()
#         nextPrint = now + 1000
#         nowPos = hub.port.E.motor.get()[1]
#         lasttimeFrameDps = (nowPos - lastPos) / ((now - lastTime) / 1000)
#         speed = hub.port.E.motor.get()[0]
#         print("dps:", lasttimeFrameDps, "rolling avg", rolling_avg)
#         lastTime = now
#         lastPos = nowPos
