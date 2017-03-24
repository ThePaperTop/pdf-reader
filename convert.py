import os, sys
from gi.repository import Poppler
import cairo
import urllib.request
from PIL import Image

def convert(fn, page_index, page_filename, threshold=127):
    url = "file://%s" % urllib.request.pathname2url(os.path.abspath(fn))

    document = Poppler.Document.new_from_file(url, password=None)

    page = document.get_page(page_index)

    width, height = page.get_size()[0], page.get_size()[1]
    landscape = width > height

    if landscape:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 480)
    else:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 480, 800)

    context = cairo.Context(surface)

    context.set_source_rgb(255, 255, 255)

    context.paint()

    if landscape:
        x_scale, y_scale = 800.0 / width, 480.0 / height
    else:
        x_scale, y_scale = 480.0 / width, 800.0 / height

    if x_scale < y_scale:
        context.scale(x_scale, x_scale)
    else:
        context.scale(y_scale, y_scale)

    page.render(context)

    png_fn = "%s.png" % page_filename
    
    surface.write_to_png(png_fn)

    img = Image.open(png_fn)

    img = img.convert("L")
    
    if landscape:
        img = img.rotate(270)
        
    img = img.point(lambda p: p > threshold and 255, "1")

    img.save(page_filename)
