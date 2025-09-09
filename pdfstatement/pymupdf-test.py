import pymupdf, subprocess, re

url = 'C:\\Users\\rokko\\Downloads\\eStmt_2025-08-05.pdf'
url_wf = 'C:\\Users\\rokko\\Downloads\\071825_WellsFargo.pdf'
location = 'C:\\Users\\rokko\\Downloads\\python\\backend\\tutorialproject\\data\\bofa_2025-08-05.pdf'

doc = pymupdf.open(url_wf)

page = doc.load_page(2)

text = page.get_text("text")
blocks = page.get_text("blocks")
words = page.get_text("html")

out_string = text
print(repr(out_string))