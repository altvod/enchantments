import curses
import unicodedata

from collections import ChainMap
from contextlib import contextmanager


def remove_control_characters(text):
    return ''.join(char for char in text if unicodedata.category(char)[0] != "C")


class EOLReached(Exception):
    def __init__(self, buffer):
        self.buffer = buffer


class InvalidPosition(Exception):
    pass


class MockScr:
    def __init__(self, h, w):
        self.h = h
        self.w = w

    def addstr(self, y, x, s):
        pass

    def getmaxyx(self):
        return self.h-1, self.w-1


class TextBuffer:
    def __init__(self, text=None):
        self.text = text or ''

    def __getitem__(self, ind):
        if not isinstance(ind, (int, slice)):
            raise TypeError('Buffer index must be an integer')
        if isinstance(ind, int) and ind > len(self.text):
            raise IndexError('Out of range')

        return self.text[ind]

    def __setitem__(self, ind, text):
        if isinstance(ind, int):
            if ind > len(self.text):
                raise IndexError('Out of range')
            if len(text) != 1:
                raise ValueError('Cannot set more that one char')
            self.text = self.text[:ind] + text + self.text[ind+1:]

        elif isinstance(ind, slice):
            if ind.step is not None and ind.step != 1:
                raise ValueError('Only step = 1 is allowed')
            self.text = self.text[:ind.start] + text + self.text[ind.stop:]

        else:
            raise TypeError('Buffer index must be an integer or slice')

    def __contains__(self, item):
        return item in self.text

    def __len__(self):
        return len(self.text)

    def append(self, text):
        self.text += text

    def insert(self, ind, text):
        if not isinstance(ind, int):
            raise TypeError('Buffer index must be an integer')
        if ind > len(self.text):
            raise IndexError('Out of range')
        self.text = self.text[:ind] + text + self.text[ind:]

    def clear(self):
        self.text = ''


class RawLine:
    __slots__ = ('stdscr', 'buffer', 'buffer_pos', 'y', '_minx', '_maxx', '_len')

    def __init__(self, stdscr, buffer, buffer_pos, y, minx=0, maxx=None):
        self.stdscr = stdscr
        self.buffer = buffer
        self.buffer_pos = buffer_pos
        self.y = y
        self._minx = minx
        self._maxx = maxx
        self._len = None

    @property
    def maxx(self):
        maxx = self._maxx if self._maxx is not None else self.stdscr.getmaxyx()[1]
        return min(maxx, self.stdscr.getmaxyx()[1])

    @property
    def minx(self):
        return min(self._minx, self.stdscr.getmaxyx()[1])

    def __len__(self):
        self._len = self._len if self._len is not None else self.maxx - self.minx + 1
        return self._len

    @property
    def buffer_end_pos(self):
        return min(len(self.buffer), self.buffer_pos + len(self))

    def move_left(self, from_x, size):
        buffer_del_pos = self.buffer_pos + (from_x - self.minx)
        overflow_size = size - (from_x - self.minx)
        overflow = self.buffer[buffer_del_pos:buffer_del_pos+overflow_size]
        self.paste(max(self.minx, from_x-size), self.buffer[buffer_del_pos+overflow_size: self.buffer_end_pos])
        buffer_len = len(self.buffer)
        if self.buffer_end_pos >= buffer_len:
            self.buffer[buffer_len-size:buffer_len] = ''
        return overflow

    def move_right(self, from_x, size):
        buffer_ins_pos = self.buffer_pos + (from_x - self.minx)
        overflow = self.buffer[self.buffer_end_pos-size:self.buffer_end_pos]
        self.paste(from_x+size, self.buffer[buffer_ins_pos:self.buffer_end_pos-size])
        return overflow

    def paste(self, from_x, text):
        """Paste text, overwriting text."""
        buffer_paste_pos = self.buffer_pos + (from_x - self.minx)
        self.stdscr.addstr(self.y, from_x, text)
        self.buffer[buffer_paste_pos:buffer_paste_pos+len(text)] = text

    def insert(self, from_x, text):
        """Paste text, moving text to the right; return overflow."""
        if from_x < self.minx or from_x > self.maxx:
            raise InvalidPosition

        fitting_len = self.maxx - from_x + 1
        fitting_text = text[:fitting_len]
        fitting_len = len(fitting_text)
        unfitting_text = text[fitting_len:]
        overflow = unfitting_text + self.move_right(from_x, fitting_len)
        self.paste(from_x, fitting_text)
        return overflow


class LineController:
    def __init__(self, stdscr, start_x, start_y, buffer=None):
        self.stdscr = stdscr
        self.start_x = start_x
        self.start_y = start_y
        self.width = self.stdscr.getmaxyx()[1] + 1
        self.buffer = buffer or TextBuffer()

        # Initialize lines
        buffer_pos = 0
        y = self.start_y
        self.lines = [
            RawLine(self.stdscr, self.buffer, buffer_pos, y, self.start_x)
        ]
        buffer_pos += len(self.lines[0])
        while buffer_pos < len(self.buffer):
            self.lines.append(
                RawLine(self.stdscr, self.buffer, buffer_pos, y, 0)
            )
            buffer_pos += len(self.lines[-1])

    def get_line(self, y):
        return self.lines[y-self.start_y]

    def pos_to_xy(self, pos):
        return (self.start_x+pos) % self.width, self.start_y + (self.start_x+pos) // self.width

    def xy_to_pos(self, x, y):
        return (y - self.start_y) * self.width - self.start_x + x

    def insert_xy(self, x, y, text):
        line = self.get_line(y)
        overflow = line.insert(x, text)
        while overflow:
            try:
                line = self.get_line(y)
            except IndexError:
                line = RawLine(self.stdscr, self.buffer, len(self.buffer), y, 0)
                self.lines.append(line)

            overflow = line.insert(0, text)
            y += 1

    def insert_pos(self, pos, text):
        x, y = self.pos_to_xy(pos)
        self.insert_xy(x, y, text)

    def delete_backward_xy(self, x, y, size):
        while size > self.width:
            self.delete_backward_xy(x, y, self.width)
            size -= self.width

        size = max(0, min(size, (y-self.start_y)*self.width - self.start_x + x))
        max_y = self.start_y + len(self.lines) - 1
        cur_y = max_y
        overflow = ''
        while cur_y >= y:
            cur_x = 0 if cur_y != y else x
            previous_overflow = overflow
            line = self.get_line(cur_y)
            overflow = line.move_left(cur_x, size)
            line.paste(len(line)-len(previous_overflow), previous_overflow)

        if overflow:
            line = self.get_line(y-1)
            line.move_left(x, size)

        if len(self.lines) > 1:
            if self.lines[-2].buffer_end_pos - self.lines[-2].buffer_pos < len(self.lines[-2]):
                del self.lines[-1]

    def delete_backward_pos(self, pos, size):
        x, y = self.pos_to_xy(pos)
        self.delete_backward_xy(x, y, size)

    def delete_pos(self, pos, size):
        for i in range(size):
            self.delete_backward_pos(pos+1, 1)

    def delete_xy(self, x, y, size):
        pos = self.xy_to_pos(x, y)
        self.delete_pos(pos, size)


class CursedStream:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.key_handler_map = ChainMap({})

        self.buffer = ''
        self.pos = 0
#        self._collapse()

    def _clear_buffer(self):
        self.buffer = ''
        self.pos = 0

    def bind_key(self, key, handler):
        """"
        Add handler for a specific key or range of keys
        The handler is added only to the current key context
        """
        if not isinstance(key, (int, str)):
            raise TypeError('Argument "key" must be an integer or a string')

        self.key_handler_map[key] = handler

    def unbind_key(self, key):
        del self.key_handler_map[key]

    @contextmanager
    def key_context(self):
        """Context manager for temporarily binding key handlers."""
        original_chainmap = self.key_handler_map
        try:
            self.key_handler_map = self.key_handler_map.new_child()
            yield

        finally:
            self.key_handler_map = original_chainmap

    def _readchar_to_buffer(self):
        """"
        Read a single character from the console.
        If there is a handler for the key, call it.
        If no handler was found and the kay is not a special key, then return it
        """
        char = self.stdscr.get_wch()
        try:
            self.key_handler_map[char]()

        except KeyError:
            if isinstance(char, str):
                self.addstr(char)

    def flush_buffer(self):
        result = self.buffer
        self._clear_buffer()
        return result

    def read(self, length=None):
        length_before = len(self.buffer)
        while length is None or len(self.buffer) - length_before < length:
            try:
                self._readchar_to_buffer()
            except EOFError:
                break

        return self.flush_buffer()

    def readline(self):
        def on_key_enter():
            buffer = self.flush_buffer()
            self.newline()
            raise EOLReached(buffer + '\n')

        with self.key_context():
            self.bind_key('\n', on_key_enter)
            try:
                return self.read()
            except EOLReached as eol:
                return eol.buffer

    def peekline(self):
        """Return contents of the buffer."""
        return self.buffer

    def addstr(self, text):
        """Add char to the buffer. Print it to the screen."""
        text = remove_control_characters(text)
        if self.pos == len(self.buffer):
            self.buffer += text
            self.stdscr.addstr(text)
            self.pos += len(text)
            self.move_cursor(0)
        else:
            self.buffer = self.buffer[:self.pos] + text + self.buffer[self.pos:]
            self.stdscr.insstr(text)
            self.move_cursor(len(text))

    def delchar(self, inc):
        """
        Delete character at the current position.
        inc must be:
            -1 for BACKSPACE-like behavior or
            0 for DELETE-like behavior
        """
        if inc not in (0, -1):
            raise ValueError('Unacceptable inc value for delchar: {0}'.format(inc))
        self.move_cursor(-1)
        self.stdscr.delch()

        self.buffer = self.buffer[:self.pos] + self.buffer[self.pos+1:]

    def clearline(self):
        """Clear the current line & buffer."""
        self.move_cursor(len(self.buffer))
        self.stdscr.clrtoeol()
        self._clear_buffer()

    def move_cursor(self, inc):
        """Move cursor to a new position within the buffer's range."""
        inc = max(0, min(len(self.buffer), self.pos+inc)) - self.pos

        old_y, old_x = self.stdscr.getyx()
        h, w = self.stdscr.getmaxyx()

        old_pos = old_y * w + old_x
        new_pos = old_pos + inc
        new_pos_x, new_pos_y = new_pos % w,  new_pos // w

        self.stdscr.move(new_pos_y, new_pos_x)
        self.pos = self.pos + inc

    def peekchar(self):
        try:
            return self.buffer[self.pos]
        except IndexError:
            return None

    def move_cursor_to_end(self):
        self.move_cursor(len(self.buffer) - self.pos)

    def newline(self):
        self.move_cursor_to_end()
        old_y, old_x = self.stdscr.getyx()

        # check window size
        h, w = self.stdscr.getmaxyx()

        if old_y == h - 1:
            # delete first line to prevent overflow
            self.stdscr.move(0, 0)
            self.stdscr.insdelln(-1)
            new_y = old_y
        else:
            new_y = old_y + 1

        self.stdscr.move(new_y, 0)
        self._clear_buffer()

    def write(self, text):
        self.move_cursor_to_end()
        while True:
            nl_ind = text.find('\n')
            if nl_ind > -1:
                self.stdscr.addstr(text[:nl_ind])
                text = text[nl_ind+1:]
                self.newline()
            else:
                self.stdscr.addstr(text)
                break

        self._clear_buffer()

    def _collapse(self):
        h, w = self.stdscr.getmaxyx()
        self.stdscr.resize(2, w)
        self.stdscr.refresh()


class EnchantedStream(CursedStream):
    def __init__(self, *args, **kwargs):
        self.is_alpha = kwargs.pop('alpha_checker', lambda char: char.isalpha())
        self.get_completion = kwargs.pop('completer', lambda line, word: '')

        super().__init__(*args, **kwargs)

        self.bind_key(curses.KEY_BACKSPACE, lambda: self.delchar(-1))
        self.bind_key(curses.KEY_DC, lambda: self.delchar(0))
        self.bind_key(curses.KEY_RIGHT, lambda: self.move_cursor(1))
        self.bind_key(curses.KEY_LEFT, lambda: self.move_cursor(-1))
#        self.bind_key(curses.KEY_TAB, self.complete)
        self.bind_key(545, lambda: self.skip_word(-1))
        self.bind_key(560, lambda: self.skip_word(1))

    def skip_word(self, inc):
        if inc not in (-1, 1):
            raise ValueError('Unacceptable inc value for skip_word: {0}'.format(inc))

        last_result = None
        while 0 <= self.pos+inc <= len(self.buffer):
            self.move_cursor(inc)
            char = self.peekchar()
            if char is None:
                break

            new_result = self.is_alpha(char)
            if last_result is not None and new_result != last_result:
                if inc == -1:
                    self.move_cursor(-inc)
                break

            last_result = new_result

    def delete_word(self, inc):
        if inc not in (-1, 0):
            raise ValueError('Unacceptable inc value for delete_word: {0}'.format(inc))

        if inc not in (-1, 1):
            raise ValueError('Unacceptable inc value for skip_word: {0}'.format(inc))

        last_result = None
        while 0 <= self.pos+inc <= len(self.buffer):
            self.move_cursor(inc)
            char = self.peekchar()
            if char is None:
                break

            new_result = self.is_alpha(char)
            if last_result is not None and new_result != last_result:
                if inc == -1:
                    self.move_cursor(-inc)
                break

            last_result = new_result

    def complete(self):
        pos = self.pos
        while pos > 0 and self.is_alpha(self.buffer[pos-1]):
            pos -= 1

        line = self.buffer[:self.pos]
        word = self.buffer[pos:self.pos]
        self.addstr(self.get_completion(line, word))


def test_curses(stdscr):
    stream = EnchantedStream(stdscr, completer=lambda line, word: word)

    while True:
        stream.write('>>> ')
        stream.write(stream.readline())


if __name__ == '__main__':
    curses.wrapper(test_curses)
