import curses
import unicodedata

from collections import ChainMap
from contextlib import contextmanager


def remove_control_characters(text):
    return ''.join(char for char in text if unicodedata.category(char)[0] != "C")


class EOLReached(Exception):
    def __init__(self, buffer):
        self.buffer = buffer


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
#        self._expand_height(text.count('\n'))
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

    def _expand_height(self, inc=1):
        h, w = self.stdscr.getmaxyx()
        self.stdscr.resize(h+inc, w)
        self.stdscr.refresh()

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