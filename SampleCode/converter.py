import docx2txt

path = r'C:\Users\usman.sajid\OneDrive - Bentley Systems, Inc\Desktop\EyeWasWord.docx'

text = docx2txt.process(path)
print(text)