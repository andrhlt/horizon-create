"""Exact comparison of Java and Horizon player food float32 state."""
from struct import pack


def same_f32(left, right):
    return pack("!f", float(left)) == pack("!f", float(right))
