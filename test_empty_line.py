from pureos.desktop.terminal import TerminalOutput
from pureos.desktop.output_capture import OutputCapture

t = TerminalOutput()
with OutputCapture(t):
    print("line1")
    print()
    print("line2")
print(t.lines)
