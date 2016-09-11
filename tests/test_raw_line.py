from unittest import TestCase

from enchantments import MockScr, TextBuffer, RawLine


class RawLineTestCase(TestCase):
    def setUp(self):
        self.text = 'abcdefghij'
        self.buffer = TextBuffer(self.text)
        self.line = RawLine(MockScr(10, 10), self.buffer, 0, 0)

    def test_paste(self):
        #    abcdefghij
        #      QWE
        #    abQWEfghij
        self.line.paste(2, 'QWE')
        self.assertEqual(self.text[:2]+'QWE'+self.text[5:], self.buffer.text)

    def test_move_left(self):
        overflow =self.line.move_left(1, 3)
        #    abcdefghij
        #  <--
        #    defghij      (overflow: bc)
        self.assertEqual(self.text[3:]+self.text[-3:], self.buffer.text)
        self.assertEqual('bc', overflow)
        self.assertEqual(10, len(self.buffer))

    def test_move_right(self):
        overflow = self.line.move_right(4, 3)
        #    abcdefghij
        #        -->
        #    abcd???efg   (overflow: hij)
        self.assertEqual(self.text[:4], self.buffer.text[:4])
        self.assertEqual(self.text[4:7], self.buffer.text[7:])
        self.assertEqual('hij', overflow)
        self.assertEqual(10, len(self.buffer))

    def test_move_right_no_overflow(self):
        self.text = 'abcdefg'
        self.buffer = TextBuffer(self.text)
        self.line = RawLine(MockScr(10, 10), self.buffer, 0, 0)

        overflow = self.line.move_right(4, 3)
        #    abcdefg
        #        -->
        #    abcd???efg   (overflow: )
        self.assertEqual(self.text[:4], self.buffer.text[:4])
        self.assertEqual(self.text[4:7], self.buffer.text[7:])
        self.assertEqual('', overflow)
        self.assertEqual(10, len(self.buffer))

    def test_insert(self):
        overflow = self.line.insert(4, 'XYZ')
        #    abcdefghij
        #        -->
        #        XYZ
        #    abcdXYZefg   (overflow: hij)
        self.assertEqual(self.text[:4]+'XYZ'+self.text[4:7], self.buffer.text)
        self.assertEqual('hij', overflow)
        self.assertEqual(10, len(self.buffer))
