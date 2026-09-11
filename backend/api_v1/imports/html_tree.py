"""Small DOM for static saved HTML. Never evaluates scripts or loads resources."""
from html.parser import HTMLParser
from dataclasses import dataclass, field


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: object = field(default=None, repr=False)

    def find_all(self, tag):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if child.tag == tag:
                    result.append(child)
                result.extend(child.find_all(tag))
        return result

    def text(self):
        if self.tag in ('script', 'style', 'svg'):
            return ''
        # MathJax includes two renderings. Use its semantic MathML once.
        if self.tag == 'mjx-container':
            math = self.find_all('math')
            if math:
                return math[0].text()
        values = [c.text() if isinstance(c, Node) else c for c in self.children]
        if self.tag in ('math', 'mrow', 'mn', 'mi', 'mo', 'mtext'):
            return ''.join(values)
        if self.tag in ('msup', 'msub'):
            return ('^' if self.tag == 'msup' else '_').join(f'({v})' for v in values if v.strip())
        if self.tag == 'mfrac':
            return '/'.join(f'({v})' for v in values if v.strip())
        return ' '.join(' '.join(values).split())


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]
        self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > 100000 or len(self.stack) > 200:
            raise ValueError('HTML structure exceeds supported limits')
        node = Node(tag, dict(attrs), parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in ('input', 'img', 'br', 'hr', 'meta', 'link', 'area', 'base', 'embed', 'source', 'wbr'):
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)
