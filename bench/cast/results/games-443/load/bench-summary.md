Chromium 153.0.8010.12. Median [min–max] of 3 cold-cache runs, ms. 0 runs failed.


### desktop, s300

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| sheets, oxipng -o6 + zopfli | 99 | 99 | 6 | 36 [29–37] | 53 [44–54] | 59 [59–65] | 2.0 | 12.3 | 3 |
| sheets, WebP lossless | 86 | 85 | 6 | 41 [40–46] | 67 [66–69] | 71 [66–73] | 2.0 | 12.3 | 3 |
| sheets + recolour, WebP lossless | 86 | 85 | 6 | 43 [42–54] | 67 [64–77] | 69 [66–69] | 2.0 | 12.3 | 3 |
| PXC1, brotli, worker | 32 | 32 | 2 | 60 [58–71] | 68 [65–80] | 57 [51–60] | 2.1 | 12.3 | 3 |
| PXC1, gzip, worker | 92 | 92 | 2 | 63 [56–66] | 71 [65–74] | 52 [46–53] | 2.1 | 12.3 | 3 |
| PXC1, brotli, main thread | 32 | 32 | 2 | 79 [72–80] | 87 [80–88] | 102 [98–105] | 17.9 | 12.3 | 3 |
| .px, brotli | 39 | 39 | 7 | 172 [171–196] | 179 [178–204] | 200 [198–225] | 19.4 | 12.3 | 3 |

### desktop, s300v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| sheets, oxipng -o6 + zopfli | 295 | 294 | 16 | 73 [68–77] | 127 [115–139] | 107 [102–130] | 2.4 | 36.9 | 3 |
| sheets, WebP lossless | 255 | 254 | 16 | 92 [85–93] | 172 [165–172] | 136 [136–138] | 2.4 | 36.9 | 3 |
| PXC1, brotli, worker | 34 | 34 | 2 | 117 [107–131] | 137 [128–163] | 75 [69–82] | 2.2 | 36.9 | 3 |
| PXC1, gzip, worker | 96 | 96 | 2 | 119 [117–119] | 142 [138–143] | 67 [66–70] | 2.2 | 36.9 | 3 |
| PXC1, brotli, main thread | 34 | 34 | 2 | 120 [115–124] | 141 [137–145] | 189 [181–192] | 54.6 | 36.9 | 3 |
| sheets + recolour, WebP lossless | 89 | 88 | 6 | 173 [166–180] | 195 [187–201] | 211 [210–217] | 28.7 | 36.9 | 3 |
| .px, brotli | 41 | 41 | 7 | 259 [247–284] | 280 [269–304] | 380 [353–390] | 59.1 | 36.9 | 3 |

### desktop, s650v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| sheets, oxipng -o6 + zopfli | 657 | 656 | 16 | 99 [92–101] | 196 [189–203] | 162 [159–166] | 2.5 | 77.5 | 3 |
| sheets, WebP lossless | 475 | 474 | 16 | 158 [146–160] | 335 [313–349] | 237 [224–248] | 2.5 | 77.5 | 3 |
| PXC1, brotli, main thread | 49 | 49 | 2 | 221 [220–231] | 266 [264–277] | 341 [339–357] | 66.6 | 77.5 | 3 |
| PXC1, gzip, worker | 190 | 190 | 2 | 241 [238–244] | 289 [280–291] | 100 [97–102] | 3.3 | 77.5 | 3 |
| PXC1, brotli, worker | 49 | 49 | 2 | 246 [238–248] | 295 [294–296] | 112 [106–114] | 3.3 | 77.5 | 3 |
| sheets + recolour, WebP lossless | 167 | 167 | 6 | 314 [304–316] | 358 [346–366] | 350 [336–359] | 7.7 | 77.5 | 3 |
| .px, brotli | 73 | 73 | 7 | 518 [501–543] | 567 [545–594] | 754 [745–816] | 73.5 | 77.5 | 3 |

### desktop-100mbps, s300

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| sheets, oxipng -o6 + zopfli | 99 | 99 | 6 | 85 [76–88] | 102 [93–106] | 64 [61–68] | 2.0 | 12.3 | 3 |
| sheets + recolour, WebP lossless | 86 | 85 | 6 | 85 [84–98] | 114 [107–133] | 76 [65–81] | 2.0 | 12.3 | 3 |
| sheets, WebP lossless | 86 | 85 | 6 | 87 [86–94] | 111 [110–119] | 71 [71–76] | 2.0 | 12.3 | 3 |
| PXC1, brotli, worker | 32 | 32 | 2 | 104 [104–112] | 112 [112–121] | 56 [54–56] | 2.1 | 12.3 | 3 |
| PXC1, gzip, worker | 92 | 92 | 2 | 107 [104–113] | 114 [112–123] | 53 [50–56] | 2.1 | 12.3 | 3 |
| PXC1, brotli, main thread | 32 | 32 | 2 | 110 [104–111] | 118 [112–118] | 108 [100–109] | 17.3 | 12.3 | 3 |
| .px, brotli | 39 | 39 | 7 | 235 [228–247] | 244 [236–256] | 233 [227–244] | 19.4 | 12.3 | 3 |

### desktop-100mbps, s300v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| sheets, oxipng -o6 + zopfli | 295 | 294 | 16 | 123 [121–131] | 179 [176–194] | 121 [113–123] | 2.4 | 36.9 | 3 |
| sheets, WebP lossless | 255 | 254 | 16 | 153 [140–155] | 229 [214–231] | 135 [130–136] | 2.4 | 36.9 | 3 |
| PXC1, brotli, main thread | 34 | 34 | 2 | 155 [146–161] | 178 [169–184] | 196 [185–202] | 54.6 | 36.9 | 3 |
| PXC1, gzip, worker | 96 | 96 | 2 | 164 [163–189] | 191 [186–211] | 77 [77–78] | 2.2 | 36.9 | 3 |
| PXC1, brotli, worker | 34 | 34 | 2 | 169 [163–171] | 196 [192–203] | 82 [80–82] | 2.3 | 36.9 | 3 |
| sheets + recolour, WebP lossless | 89 | 88 | 6 | 214 [208–246] | 234 [231–281] | 218 [218–244] | 28.8 | 36.9 | 3 |
| .px, brotli | 41 | 41 | 7 | 304 [292–320] | 326 [316–341] | 383 [381–404] | 59.0 | 36.9 | 3 |

### desktop-100mbps, s650v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| sheets, oxipng -o6 + zopfli | 657 | 656 | 16 | 169 [164–169] | 263 [259–266] | 163 [161–166] | 2.5 | 77.5 | 3 |
| sheets, WebP lossless | 475 | 474 | 16 | 224 [219–247] | 394 [371–399] | 217 [208–238] | 2.5 | 77.5 | 3 |
| PXC1, brotli, main thread | 49 | 49 | 2 | 252 [251–254] | 298 [294–298] | 340 [338–340] | 66.8 | 77.5 | 3 |
| PXC1, brotli, worker | 49 | 49 | 2 | 282 [275–308] | 332 [320–356] | 108 [104–114] | 3.3 | 77.5 | 3 |
| PXC1, gzip, worker | 190 | 190 | 2 | 295 [279–303] | 345 [324–360] | 104 [103–117] | 3.3 | 77.5 | 3 |
| sheets + recolour, WebP lossless | 167 | 167 | 6 | 345 [343–360] | 388 [386–405] | 334 [332–355] | 7.6 | 77.5 | 3 |
| .px, brotli | 73 | 73 | 7 | 574 [557–589] | 622 [603–639] | 786 [771–794] | 73.5 | 77.5 | 3 |

### desktop-20mbps, s300

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| sheets, WebP lossless | 86 | 85 | 6 | 152 [151–156] | 179 [178–187] | 76 [74–81] | 2.0 | 12.3 | 3 |
| sheets, oxipng -o6 + zopfli | 99 | 99 | 6 | 153 [147–158] | 169 [165–175] | 68 [68–70] | 2.0 | 12.3 | 3 |
| sheets + recolour, WebP lossless | 86 | 85 | 6 | 156 [146–158] | 185 [169–186] | 80 [72–87] | 2.0 | 12.3 | 3 |
| PXC1, brotli, main thread | 32 | 32 | 2 | 160 [158–162] | 167 [165–169] | 114 [102–116] | 18.0 | 12.3 | 3 |
| PXC1, brotli, worker | 32 | 32 | 2 | 160 [154–167] | 168 [161–176] | 57 [52–62] | 2.1 | 12.3 | 3 |
| PXC1, gzip, worker | 92 | 92 | 2 | 180 [176–189] | 191 [186–198] | 64 [60–64] | 2.1 | 12.3 | 3 |
| .px, brotli | 39 | 39 | 7 | 257 [254–258] | 264 [261–270] | 209 [206–215] | 19.1 | 12.3 | 3 |

### desktop-20mbps, s300v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| PXC1, brotli, main thread | 34 | 34 | 2 | 206 [206–211] | 232 [229–236] | 202 [202–208] | 54.7 | 36.9 | 3 |
| PXC1, brotli, worker | 34 | 34 | 2 | 224 [212–237] | 248 [236–258] | 79 [78–97] | 2.2 | 36.9 | 3 |
| PXC1, gzip, worker | 96 | 96 | 2 | 242 [235–270] | 266 [263–292] | 80 [74–84] | 2.2 | 36.9 | 3 |
| sheets, oxipng -o6 + zopfli | 295 | 294 | 16 | 245 [243–253] | 297 [295–307] | 116 [116–120] | 2.4 | 36.9 | 3 |
| sheets, WebP lossless | 255 | 254 | 16 | 256 [256–259] | 337 [335–367] | 141 [139–180] | 2.4 | 36.9 | 3 |
| sheets + recolour, WebP lossless | 89 | 88 | 6 | 272 [271–285] | 293 [290–305] | 213 [209–232] | 28.7 | 36.9 | 3 |
| .px, brotli | 41 | 41 | 7 | 345 [332–345] | 367 [353–369] | 377 [362–381] | 59.5 | 36.9 | 3 |

### desktop-20mbps, s650v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| PXC1, brotli, worker | 49 | 49 | 2 | 330 [320–332] | 373 [365–377] | 103 [102–105] | 3.3 | 77.5 | 3 |
| PXC1, brotli, main thread | 49 | 49 | 2 | 340 [331–349] | 390 [370–400] | 382 [370–400] | 66.7 | 77.5 | 3 |
| PXC1, gzip, worker | 190 | 190 | 2 | 382 [381–385] | 432 [428–435] | 111 [105–116] | 1.9 | 77.5 | 3 |
| sheets, WebP lossless | 475 | 474 | 16 | 383 [381–386] | 540 [532–551] | 227 [220–242] | 2.5 | 77.5 | 3 |
| sheets, oxipng -o6 + zopfli | 657 | 656 | 16 | 398 [394–405] | 496 [489–521] | 178 [175–203] | 2.5 | 77.5 | 3 |
| sheets + recolour, WebP lossless | 167 | 167 | 6 | 466 [454–473] | 517 [500–523] | 384 [374–384] | 7.6 | 77.5 | 3 |
| .px, brotli | 73 | 73 | 7 | 685 [640–690] | 729 [689–738] | 844 [804–870] | 73.5 | 77.5 | 3 |

### desktop-4g, s300

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| PXC1, brotli, main thread | 32 | 32 | 2 | 513 [513–514] | 521 [521–522] | 114 [114–118] | 17.6 | 12.3 | 3 |
| PXC1, brotli, worker | 32 | 32 | 2 | 521 [520–522] | 530 [529–534] | 60 [55–63] | 2.1 | 12.3 | 3 |
| .px, brotli | 39 | 39 | 7 | 666 [663–676] | 673 [671–684] | 220 [219–237] | 19.2 | 12.3 | 3 |
| sheets + recolour, WebP lossless | 86 | 85 | 6 | 762 [759–764] | 788 [782–790] | 82 [82–88] | 2.0 | 12.3 | 3 |
| sheets, WebP lossless | 86 | 85 | 6 | 771 [764–774] | 796 [794–800] | 83 [82–89] | 2.0 | 12.3 | 3 |
| PXC1, gzip, worker | 92 | 92 | 2 | 817 [812–828] | 825 [824–836] | 59 [57–67] | 2.1 | 12.3 | 3 |
| sheets, oxipng -o6 + zopfli | 99 | 99 | 6 | 837 [831–852] | 853 [847–872] | 75 [74–84] | 2.0 | 12.3 | 3 |

### desktop-4g, s300v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| PXC1, brotli, main thread | 34 | 34 | 2 | 591 [591–604] | 623 [616–627] | 230 [222–236] | 54.9 | 36.9 | 3 |
| PXC1, brotli, worker | 34 | 34 | 2 | 596 [588–600] | 619 [616–624] | 78 [75–87] | 2.2 | 36.9 | 3 |
| .px, brotli | 41 | 41 | 7 | 748 [737–754] | 771 [758–776] | 372 [369–386] | 58.5 | 36.9 | 3 |
| PXC1, gzip, worker | 96 | 96 | 2 | 899 [885–907] | 923 [909–931] | 82 [82–84] | 2.2 | 36.9 | 3 |
| sheets + recolour, WebP lossless | 89 | 88 | 6 | 906 [891–911] | 927 [912–932] | 226 [219–234] | 28.8 | 36.9 | 3 |
| sheets, WebP lossless | 255 | 254 | 16 | 1838 [1668–1940] | 1922 [1752–2021] | 167 [165–168] | 2.4 | 36.9 | 3 |
| sheets, oxipng -o6 + zopfli | 295 | 294 | 16 | 1888 [1858–1891] | 1940 [1909–1951] | 142 [138–149] | 2.4 | 36.9 | 3 |

### desktop-4g, s650v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| PXC1, brotli, main thread | 49 | 49 | 2 | 776 [763–787] | 821 [813–840] | 388 [385–408] | 66.6 | 77.5 | 3 |
| PXC1, brotli, worker | 49 | 49 | 2 | 803 [777–812] | 861 [821–862] | 108 [108–122] | 3.3 | 77.5 | 3 |
| .px, brotli | 73 | 73 | 7 | 1175 [1175–1218] | 1237 [1224–1266] | 800 [786–819] | 73.5 | 77.5 | 3 |
| sheets + recolour, WebP lossless | 167 | 167 | 6 | 1417 [1408–1425] | 1459 [1452–1469] | 363 [362–374] | 7.6 | 77.5 | 3 |
| PXC1, gzip, worker | 190 | 190 | 2 | 1510 [1473–1708] | 1561 [1531–1752] | 124 [113–125] | 3.3 | 77.5 | 3 |
| sheets, WebP lossless | 475 | 474 | 16 | 2750 [2747–2754] | 2916 [2911–2934] | 267 [259–283] | 2.5 | 77.5 | 3 |
| sheets, oxipng -o6 + zopfli | 657 | 656 | 16 | 3663 [3660–3670] | 3762 [3748–3767] | 206 [199–208] | 2.5 | 77.5 | 3 |

### mobile, s300

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| PXC1, brotli, worker | 32 | 32 | 2 | 599 [597–601] | 628 [628–630] | 223 [221–229] | 2.2 | 12.3 | 3 |
| PXC1, brotli, main thread | 32 | 32 | 2 | 720 [710–867] | 751 [741–896] | 485 [476–511] | 17.6 | 12.3 | 3 |
| sheets + recolour, WebP lossless | 86 | 85 | 6 | 808 [805–880] | 936 [913–980] | 344 [315–372] | 2.1 | 12.3 | 3 |
| sheets, WebP lossless | 86 | 85 | 6 | 812 [807–829] | 941 [916–948] | 363 [362–386] | 2.0 | 12.3 | 3 |
| sheets, oxipng -o6 + zopfli | 99 | 99 | 6 | 864 [863–864] | 954 [927–965] | 331 [277–363] | 2.0 | 12.3 | 3 |
| PXC1, gzip, worker | 92 | 92 | 2 | 911 [894–924] | 939 [923–963] | 248 [241–266] | 2.2 | 12.3 | 3 |
| .px, brotli | 39 | 39 | 7 | 1113 [1104–1122] | 1145 [1136–1154] | 862 [817–900] | 19.5 | 12.3 | 3 |

### mobile, s300v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| PXC1, brotli, worker | 34 | 34 | 2 | 742 [741–749] | 833 [825–863] | 314 [301–333] | 2.3 | 36.9 | 3 |
| PXC1, brotli, main thread | 34 | 34 | 2 | 948 [923–953] | 1031 [1006–1040] | 893 [854–902] | 55.0 | 36.9 | 3 |
| PXC1, gzip, worker | 96 | 96 | 2 | 1076 [1051–1094] | 1158 [1138–1212] | 314 [282–324] | 2.3 | 36.9 | 3 |
| sheets + recolour, WebP lossless | 89 | 88 | 6 | 1407 [1391–1441] | 1507 [1484–1533] | 1010 [969–1036] | 28.7 | 36.9 | 3 |
| .px, brotli | 41 | 41 | 7 | 1535 [1502–1568] | 1632 [1597–1654] | 1677 [1646–1687] | 58.3 | 36.9 | 3 |
| sheets, WebP lossless | 255 | 254 | 16 | 1694 [1692–1704] | 2091 [2091–2123] | 706 [689–711] | 2.4 | 36.9 | 3 |
| sheets, oxipng -o6 + zopfli | 295 | 294 | 16 | 1879 [1877–2091] | 2077 [2076–2298] | 492 [488–506] | 2.4 | 36.9 | 3 |

### mobile, s650v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | main thread ms | heap MB | bitmaps MB | n |
|---|---|---|---|---|---|---|---|---|---|
| PXC1, brotli, worker | 49 | 49 | 2 | 1133 [1123–1223] | 1327 [1323–1444] | 468 [457–476] | 3.3 | 77.5 | 3 |
| PXC1, brotli, main thread | 49 | 49 | 2 | 1481 [1429–1537] | 1665 [1663–1712] | 1646 [1603–1653] | 66.5 | 77.5 | 3 |
| PXC1, gzip, worker | 190 | 190 | 2 | 1854 [1819–1903] | 2042 [1989–2070] | 421 [406–425] | 3.4 | 77.5 | 3 |
| sheets + recolour, WebP lossless | 167 | 167 | 6 | 2323 [2306–2386] | 2518 [2500–2568] | 1592 [1580–1640] | 7.7 | 77.5 | 3 |
| sheets, WebP lossless | 475 | 474 | 16 | 2824 [2800–3008] | 3498 [3469–3741] | 1036 [946–1090] | 2.5 | 77.5 | 3 |
| .px, brotli | 73 | 73 | 7 | 2971 [2891–3051] | 3166 [3076–3240] | 3573 [3474–3601] | 78.1 | 77.5 | 3 |
| sheets, oxipng -o6 + zopfli | 657 | 656 | 16 | 3695 [3692–3901] | 4102 [4100–4297] | 804 [775–824] | 2.5 | 77.5 | 3 |
