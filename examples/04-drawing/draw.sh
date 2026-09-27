# A treasure chest drawn only with pxart commands, one per line, on a blank 24x20 frame.
pxart new chest.px --size 24x20 --palette palette.px
pxart rect chest.px b 2,9,20,10 --fill
pxart poly chest.px b 3,9 5,3 18,3 20,9 --fill
pxart shade chest.px --ramp Bhbo --keys b --light nw --strength 3
pxart line chest.px G 2,9 21,9 --width 2
pxart rect chest.px G 5,3,2,16 --fill
pxart rect chest.px G 17,3,2,16 --fill
pxart flood chest.px Y 5,15
pxart ellipse chest.px y 11.5,10.5,2.5,2.5 --fill
pxart poly chest.px r 11,9 12,9 12,12 11,12 --fill
pxart outline chest.px --key k --lit B
