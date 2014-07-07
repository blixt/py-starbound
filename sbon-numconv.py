#!/usr/bin/python
# -*- coding: UTF-8, tab-width: 4 -*-

from __future__ import division

from sys import argv, stdin, stdout, stderr
from starbound import sbon
import io
from json import dumps as jsonify
from urllib2 import quote as urlencode


# Examples
# =========
#  * write 42 in hex and a newline character:
#    ./sbon-numconv.py 42 10 wxc
#
#  * see how unsigned and signed numbers work:
#    for N in 0x1{,0,00,000}; do \
#       ./sbon-numconv.py ai $N dup dup w'x%09,v:x%09,V:x%0a'; done
#
#  * set a signed var-len number slot "KeyName" to 1234 in an sbon file:
#    LANG=C sed -i.bak test.sbon -rf <(./sbon-numconv.py /KeyName 1234 \
#       '("s:(\x05"c"\x04)[\x80-\xFF]*[\x00-\x7F]:\1"{V:x}%3a%0a)' cvb show)
#


def main(invocation, *cli_args):
    in_fh = stdin
    out_fh = stdout
    numstack = []
    buf = None

    cli_argi = iter(cli_args)
    for cmd in cli_argi:
        # print cmd

        # ===== Basic number I/O ==============================
        if cmd.startswith('r'):
            # read some numbers
            for numtype in cmd[1:]:
                numstack.append(in_ops[numtype](in_fh))

        if cmd.startswith('a'):
            # append some number
            for numtype in cmd[1:]:
                buf = io.BytesIO(cli_argi.next())
                numstack.append(in_ops[numtype](buf))
            continue

        if cmd.isdigit():
            numstack.append(int(cmd, 10))
            continue

        if cmd.startswith('w'):
            # write some numbers, fifo
            for buf in cmd[1:].split(','):
                buf = bufconvert(buf, numstack)
                out_fh.write(buf.getvalue())
            continue

        # ===== Advanced number stack tricks ==============================
        if cmd.startswith('/'):
            numstack.append(cmd[1:])
            continue

        if cmd.startswith('(') and cmd.endswith(')'):
            numstack.append(cmd[1:-1])
            continue

        if cmd == 'pop':
            numstack.pop()
            continue

        if cmd == 'dup':
            numstack.append(numstack[-1])
            continue

        if cmd == 'neg':
            numstack[-1] = -numstack[-1]
            continue

        if cmd == 'exch':
            numstack.append(numstack.pop(-2))   # numstack[-2:].reverse()
            continue

        if cmd == 'cvi':
            buf = io.BytesIO(numstack.pop())
            numstack.append(read_prefix_int(buf))
            continue

        if cmd == 'cvb':
            buf = numstack.pop()
            buf = bufconvert(buf, numstack)
            numstack.append(buf)
            continue

        if cmd == 'cvs':
            buf = write_char(io.BytesIO(), numstack.pop())
            numstack.append(unicode(buf.getvalue()))
            continue

        if cmd == 'show':
            write_char(out_fh, numstack.pop())
            continue

        # ===== All other commands ==============================
        raise ValueError('Unsupported command', cmd)

    if len(numstack) > 0:
        raise AssertionError('number stack not empty', numstack)


def read_prefix_int(stream):
    num = stream.readline()
    if num.startswith('0x'):
        return int(num, 16)
    if num.startswith('0'):
        return int(num, 8)
    return int(num, 10)


def read_dec_int(stream):
    return int(stream.readline(), 10)

def read_hex_int(stream):
    return int(stream.readline(), 16)

def write_dec_int(stream, num):
    stream.write(str(num))

def write_hex_int(stream, num):
    stream.write(hex(num))

def write_char(stream, num):
    if isinstance(num, (int, long,)):
        num = chr(num)
    if isinstance(num, (io.IOBase,)):
        num = num.getvalue()
    if not isinstance(num, (basestring,)):
        num = unicode(num)
    stream.write(num)
    return stream


def buftransform(buf, fmt):
    buf = buf.getvalue()
    if fmt == 'j':
        buf = jsonify(buf)
    elif fmt == 'u':
        buf = urlencode(buf)
    elif fmt == 'x':
        buf = urlencode(buf).replace('%', '\\x')
    else:
        raise KeyError('Unsupported buffer transform', fmt)
    buf = io.BytesIO(buf)
    buf.seek(0, io.SEEK_END)
    return buf


def bufconvert(fmt, nums):
    buf = io.BytesIO()
    bufstack = []
    fmt = str(fmt)
    while len(fmt) > 0:
        step, fmt = fmt[0], fmt[1:]
        if step == '{':
            bufstack.append(buf)
            buf = io.BytesIO()
            continue
        if step == '}':
            bufstack[-1].write(buf.getvalue())
            buf = bufstack.pop()
            continue
        if step == ':':
            # transform
            step, fmt = fmt[0], fmt[1:]
            buf = buftransform(buf, step)
            continue
        if step == '%':
            # urldecode
            step, fmt = fmt[0:2], fmt[2:]
            # print '%:', repr(step), 'remain:', repr(fmt)
            buf.write(chr(int(step, 16)))
            continue
        if step in ("'", '"'):
            step, fmt = fmt.split(step, 1)
            buf.write(step.encode('UTF-8'))
            continue

        try:
            step = out_ops[step]
        except KeyError:
            raise KeyError('Unsupported output format', step)

        step(buf, nums.pop(0))

    assert len(bufstack) == 0, 'Too many buffers on stack'

    return buf


in_ops = dict(
    d=read_dec_int,
    i=read_prefix_int,
    x=read_hex_int,
    v=sbon.read_varlen_number,
    V=sbon.read_varlen_number_signed,
)

out_ops = dict(
    d=write_dec_int,
    x=write_hex_int,
    c=write_char,
    v=sbon.write_varlen_number,
    V=sbon.write_varlen_number_signed,
)


if __name__ == '__main__':
    main(*argv)
