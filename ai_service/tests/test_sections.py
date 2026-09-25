import unittest
from agentfit_ai.sections import split_sections, batch_sections, SectionError

class SectionTests(unittest.TestCase):
    def test_lossless_headings_and_crlf_unicode(self):
        doc="Intro\r\n# Product\r\n"+chr(0x1f600)+" body\r\n## Stack\r\nPython\r\n# Other\r\nGo"
        sections=split_sections(doc)
        self.assertEqual("".join(x.text for x in sections),doc)
        self.assertEqual([x.path for x in sections],[(),("Product",),("Product","Stack"),("Other",)])
        self.assertEqual(sections[-1].end,len(doc))
        for a,b in zip(sections,sections[1:]):self.assertEqual(a.end,b.start)
    def test_fenced_headings_and_tables_stay_atomic(self):
        doc="# Top\n~~~python\n# not title\n\nprint(1)\n~~~\n\n| A | B |\n|---|---|\n| x | y |\n"
        sections=split_sections(doc)
        self.assertEqual(len(sections),1)
        self.assertEqual(sections[0].text,doc)
    def test_setext_and_paragraph_splitting(self):
        self.assertEqual([s.path for s in split_sections("Title\n=====\nbody\n\nSub\n---\ntext")],[("Title",),("Title","Sub")])
        doc="aaaa\n\nbbbb\n\ncccc"
        self.assertEqual("".join(s.text for s in split_sections(doc,max_chars=7)),doc)
        self.assertTrue(all(len(s.text)<=7 for s in split_sections(doc,max_chars=7)))
    def test_oversized_atomic_block_fails_without_truncation(self):
        for doc in ["x"*21,"~~~\n"+"x"*20+"\n~~~","|x|y|\n|--|--|\n|long|row|"]:
            with self.subTest(doc=doc),self.assertRaises(SectionError):
                split_sections(doc,max_chars=20)
    def test_batches_cover_all_sections_in_order(self):
        sections=split_sections("# A\na\n# B\nb\n# C\nc\n")
        batches=batch_sections(sections,max_chars=20)
        self.assertEqual(len(batches),2)
        self.assertEqual([s.id for b in batches for s in b],[s.id for s in sections])
    def test_capacity_and_blank_input_fail(self):
        with self.assertRaises(SectionError):split_sections("   ")
        with self.assertRaises(SectionError):batch_sections(split_sections("# A\naaaaa\n# B\nbbbbb\n# C\nccccc"),max_chars=11)
    def test_generated_coverage_variants(self):
        for newline in ["\n","\r\n"]:
            for prefix in ["","intro"+newline]:
                doc=prefix+newline.join(["# A","text","","## B","|a|b|","|--|--|","|x|y|","","# C","tail"])
                parts=split_sections(doc,max_chars=80)
                self.assertEqual("".join(s.text for s in parts),doc)
                self.assertEqual(parts[0].start,0)
                self.assertEqual(parts[-1].end,len(doc))

    def test_list_and_separator_do_not_become_heading(self):
        for marker in ["- Example","1. Example","> Example"]:
            doc="# Product\n"+marker+"\n---\nCurrent requirements\n"
            self.assertEqual([s.path for s in split_sections(doc)],[("Product",)])
    def test_multiline_setext_retains_entire_title(self):
        doc="Multi-line\nheading\n---\nbody"
        parts=split_sections(doc)
        self.assertEqual(parts[0].path,("Multi-line\nheading",))
        self.assertEqual(parts[0].text,doc)
