import os, sys, math
from threading import Thread
from tempfile import mkdtemp
from subprocess import Popen
from PIL import Image, ImageDraw, ImageOps
from array import *
from pervasive import PervasiveDisplay
from pil2epd import convert
from paperui.ui import *
from paperui.core import ScreenDrawer
from convert import convert
from enums import enum

converters = enum(poppler=0,
                  imagemagick=1)

class PDFReader(Form):
    def __init__(self, filename, page=0, page_size=(480, 800), converter=converters.poppler, threshold=127):
        Form.__init__(self, Widget())
        self.filename = filename
        self.page_size = page_size
        self.info = self._get_info()
        
        self.temp_dir = mkdtemp()
        self.extracted = []
        self.dirty = False
        self.page = page
        self.converter = converter
        self.threshold = threshold
        
        self.bind_key("KEY_F", lambda f, c, data: self.next_page())
        self.bind_key("KEY_RIGHT", lambda f, c, data: self.next_page())
        self.bind_key("C-KEY_F", lambda f, c, data: self.next_page())
        self.bind_key("KEY_B", lambda f, c, data: self.prev_page())
        self.bind_key("KEY_LEFT", lambda f, c, data: self.prev_page())
        self.bind_key("C-KEY_B", lambda f, c, data: self.prev_page())

        self.bind_key("KEY_HOME", lambda f, c, data: self.go_to_page(1))
        self.bind_key("KEY_END", lambda f, c, data: self.go_to_page(self.info["Pages"]))
        self.bind_key("C-KEY_HOME", lambda f, c, data: self.go_to_page(1))
        self.bind_key("C-KEY_END", lambda f, c, data: self.go_to_page(self.info["Pages"]))
        self.bind_key("KEY_Q", self._quit)

        self.popup = Popup(
            300,
            "Jump to page:",
            contents=[Spacer(height=36),
                      Entry(name="page-num"),
                      Spacer(height=36)],
            owner=self)

        self.popup.control("page-num").connect(
            "submitted",
            lambda f, c, data: self.go_to_page(int(data)))

        
        self.bind_key("KEY_G", self._show_jump_form)

    def _quit(self, *args, **kwargs):
        self.finish()

    def __destroy__(self):
        os.system("rm -rf %s" % self.temp_dir)

    def _show_jump_form(self, f, c, data):
        self.show_popup = True
        
    def _get_info(self):
        lines = os.popen("pdfinfo %s" % self.filename).readlines()

        info = {}
        
        for line in lines:
            colon_pos = line.index(":")
            key = line[:colon_pos].strip()
            value = line[colon_pos + 1:].strip()
            info[key] = value

        info["Pages"] = int(info["Pages"])
        info["Page rot"] = int(info["Page rot"])
        info["Optimized"] = info["Optimized"] == "yes"
        info["Encrypted"] = info["Encrypted"] == "yes"
        info["JavaScript"] = info["JavaScript"] == "yes"
        info["JavaScript"] = info["JavaScript"] == "yes"
        info["UserProperties"] = info["UserProperties"] == "yes"
        info["Suspects"] = info["Suspects"] == "yes"
        
        return info

    def _page_filename(self, page):
        return os.path.join(self.temp_dir,
                            "%s.pbm" % page)

    def next_page(self):
        if self.page < self.info["Pages"] - 1:
            self.page += 1
            self.view_page()

    def prev_page(self):
        if self.page > 0:
            self.page -= 1
            self.view_page()

    def go_to_page(self, page_num):
        if 0 < page_num <= self.info["Pages"]:
            self.page = page_num - 1
            self.show_popup = False
            self.view_page()
            
    def view_page(self):
        page = self.page
        if page >= self.info["Pages"]:
            return
        
        if not page in self.extracted:
            self._extract_pages(page)
            while not page in self.extracted:
                pass

        image = Image.open(self._page_filename(page))
        
        self.show(image)
    
    def _extract_pages(self, start_at):
        def do_extraction(start, pages):
            for page_num in range(start, pages):

                fn = self._page_filename(page_num)
                
                if os.path.exists(fn):
                    return
                else:
                    if self.converter == converters.imagemagick:
                        cmd = ("convert -density 300 -monochrome -geometry 480x800 -gravity center -background white -extent 480x800 %(pdf_file)s[%(page)s] %(outfile)s" %
                               {"pdf_file": self.filename,
                                "page": page_num,
                                "outfile": fn})
                        os.system(cmd)
                    elif self.converter == converters.poppler:
                        convert(self.filename,
                                page_num,
                                fn, threshold=self.threshold)
                    else:
                        raise Exception("Not implemented.")
                    
                    if page_num in self.extracted:
                        return
                    else:
                        self.extracted.append(page_num)
                        
        t = Thread(target=do_extraction,
                   args=[start_at, self.info["Pages"]],
                   daemon=True)
        t.start()

    def show(self, image):
        self.image = image
        self.dirty = True
        

    def _draw(self, drawer):
        while not self.finished:
            if self.dirty:
                self.dirty = False
                drawer.new_screen()
                drawer.image(0, 0, self.image.rotate(90))
                
                if self.show_popup:
                    self.popup.draw_contents(drawer)
                    
                drawer.send()
        exit()

    def run(self, keyboard, screen):
        self.view_page()
        Form.run(self, keyboard, screen)

if __name__ == "__main__":
    from argparse import ArgumentParser

    argp = ArgumentParser()
    
    argp.add_argument("filename",
                      help="The PDF file to display")

    argp.add_argument("-p",
                        "--page",
                        help="The initial page to display",
                        type=int,
                        default=1)
    
    argp.add_argument("-i",
                        "--imagemagick",
                        help="Use ImageMagick instead of Poppler to read the PDF",
                        action="store_true")
    
    argp.add_argument("-t",
                        "--threshold",
                        help="The threshold (0-255) above which a pixel will be white in the monochrome display",
                        type=int,
                        default=127)

    args = argp.parse_args()
    
    if args.imagemagick:
        converter = converters.imagemagick
    else:
        converter = converters.poppler
        
    reader = PDFReader(args.filename,
                       page=args.page-1,
                       threshold=args.threshold,
                       converter=converter)
    
    with ExclusiveKeyReader("/dev/input/event0") as keyboard:
        reader.run(keyboard, ScreenDrawer())

    
