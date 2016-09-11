from unittest import TestCase

from enchantments import MockScr, TextBuffer, LineController


class LineControllerTestCase(TestCase):
    def setUp(self):
        self.text = 'abcdefghij' \
                    'ABCDEFGHIJ' \
                    '0123456789'
        self.buffer = TextBuffer(self.text)
        self.controller = LineController(MockScr(10, 10), 0, 0, buffer=self.buffer)

    def test_insert_yx(self):
        self.controller.insert_yx(y=1, x=2, text='qwe')
        self.assertEqual(
            'abcdefghij'
            'ABqweCDEFG'
            'HIJ0123456'
            '789',
            self.buffer.text)
        self.assertEqual(4, len(self.controller.lines))

    def test_insert_pos(self):
        self.controller.insert_pos(pos=12, text='qwe')
        self.assertEqual(
            'abcdefghij'
            'ABqweCDEFG'
            'HIJ0123456'
            '789',
            self.buffer.text)
        self.assertEqual(4, len(self.controller.lines))

    def test_delete_backward_yx(self):
        self.controller.delete_backward_yx(y=2, x=7, size=3)
        self.assertEqual(
            'abcdefghij'
            'ABCDEFGHIJ'
            '0123789',
            self.buffer.text)
        self.assertEqual(3, len(self.controller.lines))

        self.controller.delete_backward_yx(y=1, x=5, size=3)
        self.assertEqual(
            'abcdefghij'
            'ABFGHIJ012'
            '3789',
            self.buffer.text)
        self.assertEqual(3, len(self.controller.lines))

        self.controller.delete_backward_yx(y=1, x=1, size=3)
        self.assertEqual(
            'abcdefghBF'
            'GHIJ012378'
            '9',
            self.buffer.text)
        self.assertEqual(3, len(self.controller.lines))

        self.controller.delete_backward_yx(y=0, x=2, size=2)
        self.assertEqual(
            'cdefghBFGH'
            'IJ0123789',
            self.buffer.text)
        self.assertEqual(2, len(self.controller.lines))
