import sys
import os
import time
import threading
import termios
import tty
import cv2
import pyprind


class CharFrame:
    # Define the characters to be used for creating ASCII art
    ascii_char = (
        "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
    )

    # Convert pixel luminance to an ASCII character
    def pixelToChar(self, luminance):
        return self.ascii_char[int(luminance / 256 * len(self.ascii_char))]

    # Convert a regular frame to an ASCII character frame
    def convert(self, img, limitSize=-1, fill=False, wrap=False):
        if limitSize != -1 and (
            img.shape[0] > limitSize[1] or img.shape[1] > limitSize[0]
        ):
            img = cv2.resize(img, limitSize, interpolation=cv2.INTER_AREA)
        ascii_frame = ""
        blank = ""
        if fill:
            blank += " " * (limitSize[0] - img.shape[1])
        if wrap:
            blank += "\n"
        for i in range(img.shape[0]):
            for j in range(img.shape[1]):
                ascii_frame += self.pixelToChar(img[i, j])
            ascii_frame += blank
        return ascii_frame


class I2Char(CharFrame):
    result = None

    def __init__(self, path, limitSize=-1, fill=False, wrap=False):
        self.genCharImage(path, limitSize, fill, wrap)

    def genCharImage(self, path, limitSize=-1, fill=False, wrap=False):
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return
        self.result = self.convert(img, limitSize, fill, wrap)

    def show(self, stream=2):
        if self.result is None:
            return
        if stream == 1 and os.isatty(sys.stdout.fileno()):
            self.streamOut = sys.stdout.write
            self.streamFlush = sys.stdout.flush
        elif stream == 2 and os.isatty(sys.stderr.fileno()):
            self.streamOut = sys.stderr.write
            self.streamFlush = sys.stderr.flush
        elif hasattr(stream, "write"):
            self.streamOut = stream.write
            self.streamFlush = stream.flush
        self.streamOut(self.result)
        self.streamFlush()
        self.streamOut("\n")


class V2Char(CharFrame):
    charVideo = []
    timeInterval = 0.033

    def __init__(self, path):
        if path.endswith("txt"):
            self.load(path)
        else:
            self.genCharVideo(path)

    def genCharVideo(self, filepath):
        self.charVideo = []
        cap = cv2.VideoCapture(filepath)
        self.timeInterval = round(1 / cap.get(5), 3)
        nf = int(cap.get(7))
        print("Generate char video, please wait...")
        for i in pyprind.prog_bar(range(nf)):
            rawFrame = cv2.cvtColor(cap.read()[1], cv2.COLOR_BGR2GRAY)
            frame = self.convert(rawFrame, os.get_terminal_size(), fill=True)
            self.charVideo.append(frame)
        cap.release()

    def export(self, filepath):
        if not self.charVideo:
            return
        with open(filepath, "w") as f:
            for frame in self.charVideo:
                # Add a newline character to separate each frame
                f.write(frame + "\n")

    def load(self, filepath):
        self.charVideo = []
        # Each line represents a frame
        for i in open(filepath):
            self.charVideo.append(i[:-1])

    def play(self, stream=1):
        # Bug:
        # Cursor positioning escape codes are not compatible with Windows
        if not self.charVideo:
            return
        if stream == 1 and os.isatty(sys.stdout.fileno()):
            self.streamOut = sys.stdout.write
            self.streamFlush = sys.stdout.flush
        elif stream == 2 and os.isatty(sys.stderr.fileno()):
            self.streamOut = sys.stderr.write
            self.streamFlush = sys.stderr.flush
        elif hasattr(stream, "write"):
            self.streamOut = stream.write
            self.streamFlush = stream.flush

        old_settings = None
        breakflag = None
        # Get the file descriptor for standard input
        fd = sys.stdin.fileno()

        def getChar():
            nonlocal breakflag
            nonlocal old_settings
            # Save the attributes of standard input
            old_settings = termios.tcgetattr(fd)
            # Set standard input to raw mode
            tty.setraw(sys.stdin.fileno())
            # Read a character
            ch = sys.stdin.read(1)
            breakflag = True if ch else False

        # Create a thread
        getchar = threading.Thread(target=getChar)
        # Set it as a daemon thread
        getchar.daemon = True
        # Start the daemon thread
        getchar.start()
        # Output the character frame
        rows = len(self.charVideo[0]) // os.get_terminal_size()[0]
        for frame in self.charVideo:
            # Exit the loop if input is received
            if breakflag is True:
                break
            self.streamOut(frame)
            self.streamFlush()
            time.sleep(self.timeInterval)
            # Move the cursor up 'rows-1' lines to return to the beginning
            self.streamOut("\033[{}A\r".format(rows - 1))
        # Restore standard input to its original attributes
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Move the cursor down 'rows-1' lines to the last line and clear it
        self.streamOut("\033[{}B\033[K".format(rows - 1))
        # Clear all lines of the last frame (starting from the second-to-last line)
        for i in range(rows - 1):
            # Move the cursor up one line
            self.streamOut("\033[1A")
            # Clear the current line where the cursor is
            self.streamOut("\r\033[K")
        info = "User interrupt!\n" if breakflag else "Finished!\n"
        self.streamOut(info)


if __name__ == "__main__":
    import argparse

    # Set up command-line argument parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Video file or charvideo file")
    parser.add_argument(
        "-e", "--export", nargs="?", const="charvideo.txt", help="Export charvideo file"
    )
    # Get the command-line arguments
    args = parser.parse_args()
    v2char = V2Char(args.file)
    if args.export:
        v2char.export(args.export)
    v2char.play()
