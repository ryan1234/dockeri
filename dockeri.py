#!/usr/bin/env python
import curses
import sys
import subprocess
import os
from subprocess import Popen, PIPE

class BoxSelector:
    def __init__(self, L):
        self.L = L
        self._windows = []
        self._init_curses()

    def refresh(self):
        del self._windows
        self.pad = curses.newpad(self.PAD_HEIGHT, self.PAD_WIDTH)
        self._windows = self._make_textboxes()
        picked = self._select_textbox()

    def _init_curses(self):
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.stdscr.keypad(1)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)
        self.stdscr.bkgd(curses.color_pair(2))
        self.stdscr.refresh()

        maxy, maxx = self.stdscr.getmaxyx()

        self.PAD_WIDTH = maxx
        self.PAD_HEIGHT = maxy
        self.TEXTBOX_WIDTH = 80
        self.TEXTBOX_HEIGHT = 1

        self.pad = curses.newpad(self.PAD_HEIGHT, self.PAD_WIDTH)

    def _end_curses(self):
        curses.nocbreak()
        self.stdscr.keypad(0)
        curses.echo()
        curses.endwin()

    def _make_textboxes(self):
        maxy, maxx = self.stdscr.getmaxyx()

        windows = []
        i = 1
        for s in self.L:
            windows.append(self.pad.derwin(self.TEXTBOX_HEIGHT, self.TEXTBOX_WIDTH, i, self.TEXTBOX_WIDTH))
            i += 1

        for k in range(len(windows)):
            windows[k].addstr(str(self.L[k]))

        self.status_window = self.pad.derwin(1, self.TEXTBOX_WIDTH, i + 19, self.TEXTBOX_WIDTH)
        self.status_window.bkgd(curses.color_pair(3))

        menu_window = self.pad.derwin(1, self.TEXTBOX_WIDTH, i + 20, self.TEXTBOX_WIDTH)
        menu_window.bkgd(curses.color_pair(3))
        menu_window.addstr("c = connect | r = remove | s = stop                 q = quit")

        return windows

    def _refresh_view(self, window):
        cy, cx = window.getbegyx()
        maxy, maxx = self.stdscr.getmaxyx()
        self.pad.refresh(cy, cx, 1, 1, maxy, maxx)

    def _select_textbox(self):
        windows = self._windows
        self._refresh_view(windows[0])
        topy, topx = windows[0].getbegyx()

        current_selected = 0
        last = len(self.L) - 1
        top_textbox = windows[0]

        while True:
            windows[last].bkgd(curses.color_pair(2))
            windows[current_selected].bkgd(curses.color_pair(1))

            maxy, maxx = self.stdscr.getmaxyx()
            cy, cx = windows[current_selected].getbegyx()

            if ((topy + maxy - self.TEXTBOX_HEIGHT) <= cy):
                top_textbox = windows[current_selected]

            if topy >= cy + self.TEXTBOX_HEIGHT:
                top_textbox = windows[current_selected]

            if last != current_selected:
                last = current_selected

            self._refresh_view(top_textbox)




            c = self.stdscr.getch()

            if c == curses.KEY_DOWN:
                if current_selected >= len(windows) - 1:
                    current_selected = 0
                else:
                    current_selected += 1

            elif c == curses.KEY_UP:
                if current_selected <= 0:
                    current_selected = len(windows) - 1
                else:
                    current_selected -= 1

            elif c == ord('c'):
                # Shut down so we can quit the program and open a shell into the container
                self._end_curses()

                container_id = L[int(current_selected)].split(" ")[0]
                subprocess.call("docker exec -it " + container_id + " /bin/bash", shell = True)
                sys.exit(0)

            elif c == ord('r'):
                container_id = L[int(current_selected)].container_id

                self.status_window.clear()
                self.status_window.addstr("removing container " + container_id)
                self._refresh_view(top_textbox)

                FNULL = open(os.devnull, 'w')
                subprocess.call("docker rm " + container_id, stdout = FNULL, shell = True)

                self.status_window.clear()
                self.status_window.addstr("container removed")
                self._refresh_view(top_textbox)

                del self.L
                self.L = DockerContainers().get_containers()
                self.refresh()

            elif c == ord('s'):
                container_id = L[int(current_selected)].split(" ")[0]

                self.status_window.clear()
                self.status_window.addstr("stopping container " + container_id)
                self._refresh_view(top_textbox)

                FNULL = open(os.devnull, 'w')
                subprocess.call("docker stop " + container_id, stdout = FNULL, shell = True)

                self.status_window.clear()
                self.status_window.addstr("container stopped")
                self._refresh_view(top_textbox)

                del self.L
                self.L = DockerContainers().get_containers()
                self.refresh()

            elif c == ord('q'): # Quit without selecting.
                self._end_curses()
                sys.exit(0)


class DockerContainers:
    def get_containers(self):
        running_containers = self._get_running_containers()
        stopped_containers = self._get_stopped_containers(running_containers)

        return running_containers + stopped_containers

    def _get_stopped_containers(self, running_containers):
        proc = Popen(["docker", "ps", "-a"], stdout=PIPE)
        output = proc.communicate()[0]
        lines = output.split("\n")

        containers = []
        for line in lines[1:len(lines) - 1]:
            tokens = filter(None, line.split(" "))

            container_id = tokens[0]
            image_name = tokens[1]
            name = tokens[len(tokens) - 1]

            if not any(rc.container_id == container_id for rc in running_containers):
                containers.append(DockerContainer(container_id, image_name, name, "[S]"))

        return containers

    def _get_running_containers(self):
        proc = Popen(["docker", "ps"], stdout=PIPE)
        output = proc.communicate()[0]
        lines = output.split("\n")

        containers = []
        for line in lines[1:len(lines) - 1]:
            tokens = filter(None, line.split(" "))

            container_id = tokens[0]
            image_name = tokens[1]
            name = tokens[len(tokens) - 1]

            containers.append(DockerContainer(container_id, image_name, name, "[R]"))

        return containers

class DockerContainer:
    def __init__(self, container_id, image_name, container_name, status):
        self.container_id = container_id
        self.image_name = image_name
        self.container_name = container_name
        self.status = status

    def __repr__(self):
        return self.status + " " + self.image_name.ljust(20) + " " + self.container_name

if __name__ == '__main__':
    L = DockerContainers().get_containers()
    print(L)
    BoxSelector(L).refresh()
