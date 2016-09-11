from unittest import TestCase

from enchantments import TextBuffer


class TextBufferTestCase(TestCase):
    def setUp(self):
        self.text = 'abcdefghij'
        self.buffer = TextBuffer(self.text)

    def test___getitem__(self):
        self.assertEqual('c', self.buffer[2])
        self.assertEqual('def', self.buffer[3:6])

    def test___setitem__(self):
        self.buffer[2] = 'Q'
        self.assertEqual('bQd', self.buffer.text[1:4])

        self.buffer[5:8] = 'ERT'
        self.assertEqual('eERTi', self.buffer.text[4:9])

    def test___contains__(self):
        self.assertIn('cde', self.buffer)
        self.assertNotIn('CDE', self.buffer)

    def test___len__(self):
        self.assertEqual(10, len(self.buffer))

    def test_append(self):
        self.buffer.append('qwerty')
        self.assertEqual(self.text+'qwerty', self.buffer.text)

    def test_insert(self):
        self.buffer.insert(2, 'qwe')
        self.assertEqual(self.text[:2]+'qwe'+self.text[2:], self.buffer.text)

    def test_clear(self):
        self.buffer.clear()
        self.assertEqual('', self.buffer.text)

    def test_grow(self):
        self.buffer.grow(5)
        self.assertEqual(self.text+' '*5, self.buffer.text)
