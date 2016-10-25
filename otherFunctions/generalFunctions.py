
# imports
from itertools import tee, izip
import math


# make iterator from a list
# make feature list


def listIterator(any_list):
    for i in any_list:
        yield i


# source: https://docs.python.org/2/library/itertools.html
# make pair of current and next item in a list

def pairwise(iterable):
    a, b = tee(iterable)
    next(b, None)
    return izip(a, b)


# function to add tolerance (deal with OSM and other decimal precision issues)
def keep_decimals(number, number_decimals):
    integer_part = abs(int(number))
    decimal_part = str(abs(int((number - integer_part) * (10 ** number_decimals))))
    if len(decimal_part) < number_decimals:
        zeros = str(0) * int((number_decimals - len(decimal_part)))
        decimal_part = zeros + decimal_part
    decimal = (str(integer_part) + '.' + decimal_part[0:number_decimals])
    if number < 0:
        decimal = ('-' + str(integer_part) + '.' + decimal_part[0:number_decimals])
    return decimal


def keep_decimals_string(string, number_decimals):
    integer_part = string.split(".")[0]
    # if the input is an integer there is no decimal part
    if len(string.split("."))== 1:
        decimal_part = str(0)*number_decimals
    else:
        decimal_part = string.split(".")[1][0:number_decimals]
    if len(decimal_part) < number_decimals:
        zeros = str(0) * int((number_decimals - len(decimal_part)))
        decimal_part = decimal_part + zeros
    decimal = integer_part + '.' + decimal_part
    return decimal

def snap_coord(coord, tolerance):
    return int(coord * (10 ** tolerance)) * (10**(tolerance - 2*tolerance))


# find midpoint between two points

def mid(pt1, pt2):
    x = (pt1.x() + pt2.x()) / 2
    y = (pt1.y() + pt2.y()) / 2
    return (x, y)


def angle_3_points(inter_point, vertex1, vertex2):
    inter_vertex1 = math.hypot(abs(inter_point.asPoint()[0] - vertex1[0]),
                               abs(inter_point.asPoint()[1] - vertex1[1]))
    inter_vertex2 = math.hypot(abs(inter_point.asPoint()[0] - vertex2[0]),
                               abs(inter_point.asPoint()[1] - vertex2[1]))
    vertex1_2 = math.hypot(abs(vertex1[0] - vertex2[0]), abs(vertex1[1] - vertex2[1]))
    A = ((inter_vertex1 ** 2) + (inter_vertex2 ** 2) - (vertex1_2 ** 2))
    B = (2 * inter_vertex1 * inter_vertex2)
    if B != 0:
        cos_angle = A / B
    else:
        cos_angle = NULL
    if cos_angle < -1:
        cos_angle = int(-1)
    if cos_angle > 1:
        cos_angle = int(1)
    return math.acos(cos_angle)
