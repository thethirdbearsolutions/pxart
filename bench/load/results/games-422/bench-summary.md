
### desktop, s300

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| sheets, Pillow palette PNG | 164 | 164 | 6 | 10 [9–12] | 17 [15–22] | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 141 | 141 | 6 | 13 [10–25] | 20 [16–32] | 3 |
| sheets + recolour, Pillow palette PNG | 164 | 164 | 6 | 14 [14–21] | 24 [20–28] | 3 |
| sheets, WebP lossless | 108 | 108 | 6 | 15 [11–16] | 25 [23–26] | 3 |
| sheets, oxipng -o6 + zopfli | 141 | 141 | 6 | 20 [11–21] | 26 [17–27] | 3 |
| sheets + recolour, WebP lossless | 108 | 108 | 6 | 28 [17–30] | 38 [25–40] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 357 | 347 | 301 | 42 [37–64] | 52 [47–74] | 3 |
| per-frame WebP lossless | 321 | 311 | 301 | 42 [34–43] | 58 [50–58] | 3 |
| per-frame PNG, as published (Pillow) | 811 | 802 | 301 | 50 [43–82] | 65 [60–97] | 3 |
| .px, gzip | 159 | 159 | 7 | 81 [76–81] | 85 [81–85] | 3 |
| .px, brotli | 59 | 58 | 7 | 81 [79–83] | 85 [83–87] | 3 |

### desktop, s300v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| sheets, WebP lossless | 320 | 319 | 16 | 14 [8–15] | 37 [32–42] | 3 |
| sheets, Pillow palette PNG | 488 | 488 | 16 | 15 [9–23] | 32 [29–40] | 3 |
| sheets, oxipng -o6 + zopfli | 420 | 419 | 16 | 15 [15–16] | 33 [29–33] | 3 |
| sheets + recolour, Pillow palette PNG | 168 | 168 | 6 | 102 [101–105] | 115 [114–118] | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 146 | 145 | 6 | 103 [102–105] | 114 [114–118] | 3 |
| per-frame PNG, as published (Pillow) | 2426 | 2398 | 901 | 108 [107–120] | 152 [148–165] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 1066 | 1038 | 901 | 108 [107–115] | 136 [134–140] | 3 |
| sheets + recolour, WebP lossless | 112 | 112 | 6 | 109 [109–112] | 126 [124–129] | 3 |
| .px, brotli | 62 | 62 | 7 | 110 [109–115] | 115 [115–120] | 3 |
| per-frame WebP lossless | 957 | 929 | 901 | 110 [110–112] | 157 [155–160] | 3 |
| .px, gzip | 167 | 167 | 7 | 112 [110–113] | 118 [116–127] | 3 |

### desktop, s650v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| sheets, Pillow palette PNG | 1063 | 1062 | 16 | 16 [11–28] | 55 [40–59] | 3 |
| sheets, WebP lossless | 530 | 529 | 16 | 17 [14–26] | 63 [55–66] | 3 |
| sheets, oxipng -o6 + zopfli | 918 | 917 | 16 | 18 [16–24] | 50 [48–60] | 3 |
| sheets + recolour, Pillow palette PNG | 364 | 364 | 6 | 156 [155–156] | 182 | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 316 | 315 | 6 | 158 [155–160] | 185 [182–186] | 3 |
| sheets + recolour, WebP lossless | 186 | 186 | 6 | 173 [170–173] | 203 [200–204] | 3 |
| per-frame WebP lossless | 2166 | 2107 | 1918 | 225 [224–226] | 318 [318–321] | 3 |
| per-frame PNG, as published (Pillow) | 5565 | 5505 | 1918 | 229 [223–230] | 308 [301–312] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 2404 | 2344 | 1918 | 234 [227–253] | 284 [280–306] | 3 |
| .px, gzip | 322 | 322 | 7 | 260 [256–265] | 269 [267–275] | 3 |
| .px, brotli | 93 | 93 | 7 | 265 [264–270] | 274 [274–280] | 3 |

### desktop-4g, s300

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| .px, brotli | 59 | 58 | 7 | 695 [689–722] | 700 [693–726] | 3 |
| sheets, WebP lossless | 108 | 108 | 6 | 880 [877–881] | 890 [887–890] | 3 |
| sheets + recolour, WebP lossless | 108 | 108 | 6 | 894 [892–895] | 917 [913–920] | 3 |
| sheets, oxipng -o6 + zopfli | 141 | 141 | 6 | 1049 [1043–1050] | 1056 [1050–1058] | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 141 | 141 | 6 | 1070 [1062–1074] | 1086 [1079–1094] | 3 |
| sheets, Pillow palette PNG | 164 | 164 | 6 | 1150 [1148–1157] | 1158 [1158–1164] | 3 |
| sheets + recolour, Pillow palette PNG | 164 | 164 | 6 | 1171 [1167–1171] | 1186 [1178–1188] | 3 |
| .px, gzip | 159 | 159 | 7 | 1200 [1198–1204] | 1204 [1204–1210] | 3 |
| per-frame WebP lossless | 321 | 311 | 301 | 2818 [2815–2821] | 2847 [2833–2862] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 357 | 347 | 301 | 2932 [2922–2933] | 2959 [2948–2960] | 3 |
| per-frame PNG, as published (Pillow) | 811 | 802 | 301 | 5436 [5426–5437] | 5470 [5464–5472] | 3 |

### desktop-4g, s300v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| .px, brotli | 62 | 62 | 7 | 778 [777–780] | 783 [782–786] | 3 |
| sheets + recolour, WebP lossless | 112 | 112 | 6 | 1028 [1009–1032] | 1046 [1026–1048] | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 146 | 145 | 6 | 1190 [1186–1203] | 1208 [1199–1220] | 3 |
| .px, gzip | 167 | 167 | 7 | 1290 [1289–1301] | 1296 [1295–1306] | 3 |
| sheets + recolour, Pillow palette PNG | 168 | 168 | 6 | 1306 [1300–1307] | 1320 [1313–1320] | 3 |
| sheets, WebP lossless | 320 | 319 | 16 | 1984 [1977–1995] | 2031 [2012–2051] | 3 |
| sheets, oxipng -o6 + zopfli | 420 | 419 | 16 | 2501 [2499–2505] | 2542 [2541–2547] | 3 |
| sheets, Pillow palette PNG | 488 | 488 | 16 | 2814 [2813–2817] | 2855 [2852–2864] | 3 |
| per-frame WebP lossless | 957 | 929 | 901 | 7709 [7709–7718] | 7785 [7785–7803] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 1066 | 1038 | 901 | 8108 [8100–8116] | 8164 [8155–8171] | 3 |
| per-frame PNG, as published (Pillow) | 2426 | 2398 | 901 | 15604 [15601–15613] | 15675 [15645–15685] | 3 |

### desktop-4g, s650v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| .px, brotli | 93 | 93 | 7 | 1066 [1064–1069] | 1076 [1074–1079] | 3 |
| sheets + recolour, WebP lossless | 186 | 186 | 6 | 1437 [1425–1449] | 1469 [1460–1481] | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 316 | 315 | 6 | 2092 [2086–2102] | 2120 [2114–2130] | 3 |
| .px, gzip | 322 | 322 | 7 | 2216 [2216–2222] | 2227 [2225–2232] | 3 |
| sheets + recolour, Pillow palette PNG | 364 | 364 | 6 | 2333 [2330–2334] | 2361 [2360–2362] | 3 |
| sheets, WebP lossless | 530 | 529 | 16 | 3010 [3008–3018] | 3082 [3078–3089] | 3 |
| sheets, oxipng -o6 + zopfli | 918 | 917 | 16 | 4983 [4977–4986] | 5044 [5039–5049] | 3 |
| sheets, Pillow palette PNG | 1063 | 1062 | 16 | 5689 [5675–5690] | 5748 [5742–5756] | 3 |
| per-frame WebP lossless | 2166 | 2107 | 1918 | 16454 [16452–16456] | 16566 [16562–16570] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 2404 | 2344 | 1918 | 17254 [17253–17257] | 17328 [17317–17329] | 3 |
| per-frame PNG, as published (Pillow) | 5565 | 5505 | 1918 | 34161 [34143–34161] | 34245 [34239–34256] | 3 |

### mobile, s300

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| .px, brotli | 59 | 58 | 7 | 887 [884–895] | 896 [890–903] | 3 |
| sheets, WebP lossless | 108 | 108 | 6 | 888 [884–889] | 914 [911–916] | 3 |
| sheets + recolour, WebP lossless | 108 | 108 | 6 | 895 [894–900] | 921 [921–926] | 3 |
| sheets, oxipng -o6 + zopfli | 141 | 141 | 6 | 1060 [1050–1068] | 1077 [1065–1086] | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 141 | 141 | 6 | 1062 [1055–1063] | 1078 [1071–1078] | 3 |
| sheets, Pillow palette PNG | 164 | 164 | 6 | 1157 [1155–1157] | 1174 [1170–1176] | 3 |
| sheets + recolour, Pillow palette PNG | 164 | 164 | 6 | 1166 [1164–1176] | 1180 [1180–1191] | 3 |
| .px, gzip | 159 | 159 | 7 | 1412 [1389–1420] | 1420 [1396–1427] | 3 |
| per-frame WebP lossless | 321 | 311 | 301 | 2820 [2812–2822] | 2874 [2867–2875] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 357 | 347 | 301 | 2917 [2917–2925] | 2948 [2946–2955] | 3 |
| per-frame PNG, as published (Pillow) | 811 | 802 | 301 | 5423 [5421–5432] | 5471 [5470–5478] | 3 |

### mobile, s300v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| .px, brotli | 62 | 62 | 7 | 1046 [1037–1061] | 1053 [1047–1070] | 3 |
| sheets + recolour, WebP lossless | 112 | 112 | 6 | 1274 [1269–1279] | 1318 [1315–1322] | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 146 | 145 | 6 | 1437 [1430–1445] | 1471 [1464–1476] | 3 |
| sheets + recolour, Pillow palette PNG | 168 | 168 | 6 | 1536 [1527–1537] | 1569 [1560–1574] | 3 |
| .px, gzip | 167 | 167 | 7 | 1571 [1554–1575] | 1580 [1564–1587] | 3 |
| sheets, WebP lossless | 320 | 319 | 16 | 1985 [1983–1992] | 2071 [2070–2078] | 3 |
| sheets, oxipng -o6 + zopfli | 420 | 419 | 16 | 2500 [2495–2501] | 2548 [2542–2549] | 3 |
| sheets, Pillow palette PNG | 488 | 488 | 16 | 2815 [2814–2816] | 2860 [2859–2862] | 3 |
| per-frame WebP lossless | 957 | 929 | 901 | 7710 [7706–7710] | 7872 [7866–7876] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 1066 | 1038 | 901 | 8109 [8100–8109] | 8196 [8187–8198] | 3 |
| per-frame PNG, as published (Pillow) | 2426 | 2398 | 901 | 15609 [15606–15609] | 15748 [15747–15748] | 3 |

### mobile, s650v2

| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms | n |
|---|---|---|---|---|---|---|
| .px, brotli | 93 | 93 | 7 | 1824 [1807–1837] | 1844 [1823–1854] | 3 |
| sheets + recolour, WebP lossless | 186 | 186 | 6 | 1893 [1892–1903] | 1986 [1985–1993] | 3 |
| sheets + recolour, oxipng -o6 + zopfli | 316 | 315 | 6 | 2523 [2521–2525] | 2600 [2594–2606] | 3 |
| sheets + recolour, Pillow palette PNG | 364 | 364 | 6 | 2750 [2744–2755] | 2824 [2822–2827] | 3 |
| .px, gzip | 322 | 322 | 7 | 2962 [2943–2971] | 2978 [2959–2986] | 3 |
| sheets, WebP lossless | 530 | 529 | 16 | 3006 [3004–3013] | 3180 [3177–3183] | 3 |
| sheets, oxipng -o6 + zopfli | 918 | 917 | 16 | 4987 [4981–4999] | 5099 [5089–5135] | 3 |
| sheets, Pillow palette PNG | 1063 | 1062 | 16 | 5691 [5678–5693] | 5792 [5778–5796] | 3 |
| per-frame WebP lossless | 2166 | 2107 | 1918 | 16455 [16448–16465] | 16809 [16798–16817] | 3 |
| per-frame PNG, oxipng -o6 + zopfli | 2404 | 2344 | 1918 | 17248 [17245–17260] | 17434 [17423–17446] | 3 |
| per-frame PNG, as published (Pillow) | 5565 | 5505 | 1918 | 34165 [34164–34171] | 34452 [34450–34466] | 3 |
