// Dead Route R8-F pixel textures. Bake with: node art/environment/bake-neighborhood.cjs
// The map is stored at half screen scale. Image y is 720 - world y * 0.3.
const path = require('node:path')
const assert = require('node:assert/strict')
const sharp = require('sharp')

const output = path.resolve(__dirname, '../../game/assets/neighborhood')
const neutral = [144, 144, 144]
const roads = require('../../game/assets/neighborhood/roads.json')

function texture(width, height, channels = 3) {
  const data = Buffer.alloc(width * height * channels)
  function point(x, y, color) {
    if (x >= 0 && x < width && y >= 0 && y < height) {
      data.set(color, (y * width + x) * channels)
    }
  }
  function rect(x, y, w, h, color) {
    for (let row = y; row < y + h; row++) {
      for (let col = x; col < x + w; col++) point(col, row, color)
    }
  }
  return {width, height, channels, data, point, rect}
}

function hash(x, y) {
  const bits = Math.imul(x + 29, 374761393) ^ Math.imul(y + 73, 668265263)
  return (Math.imul(bits ^ (bits >>> 13), 1274126177) >>> 0) % 97
}

function shade(color, delta) {
  return color.map(channel => Math.min(255, Math.max(0, channel + delta)))
}

function grain(image, x, y, w, h, color, strength = 1) {
  for (let row = y; row < y + h; row++) {
    for (let col = x; col < x + w; col++) {
      const noise = hash(col, row)
      const delta = noise < 7 ? -8 : noise < 20 ? -3 : noise > 88 ? 6 : 0
      image.point(col, row, shade(color, delta * strength))
    }
  }
}

function slabs(image, x, y, w, h) {
  grain(image, x, y, w, h, [166, 161, 148])
  for (let row = 1; row < h; row += 7) {
    image.rect(x, y + row, w, 1, [135, 132, 121])
    const offset = row % 2 === 0 ? 10 : 0
    for (let col = 4 + offset; col < w; col += 19) {
      image.rect(x + col, y + row + 1, 1, Math.min(6, h - row - 1), [141, 138, 127])
    }
  }
}

function southwestBlock() {
  const image = texture(860, 360)
  const {rect, point, width, height, data} = image
  rect(0, 0, width, height, neutral)
  grain(image, 0, 196, 369, 164, [115, 122, 105], 1.5)
  // Rear walk and the alley follow the open spaces between wall footprints.
  slabs(image, 16, 204, 307, 9)
  grain(image, 114, 213, 41, 101, [149, 146, 135], 1.5)
  rect(114, 214, 1, 99, [178, 168, 148])
  rect(154, 214, 1, 99, [111, 111, 102])
  for (let y = 220; y < 309; y += 13) {
    rect(119, y, 29, 1, [133, 130, 119])
    point(149, y + 1, [122, 124, 109])
  }

  // Short driveways connect the curb to each facade. Their outer edges sit on the ground.
  grain(image, 74, 267, 26, 47, [152, 146, 129])
  grain(image, 216, 291, 26, 23, [149, 146, 133])
  rect(74, 267, 1, 46, [179, 167, 141])
  rect(99, 267, 1, 46, [127, 125, 110])
  rect(216, 291, 1, 22, [174, 168, 150])
  rect(241, 291, 1, 22, [124, 122, 110])

  slabs(image, 0, 313, 369, 11)
  grain(image, 0, 324, 369, 25, [109, 113, 117], 1.5)
  rect(0, 324, 369, 1, [199, 192, 169])
  rect(0, 325, 369, 1, [129, 124, 113])
  rect(0, 348, 369, 1, [151, 149, 137])
  for (let x = 12; x < 360; x += 43) rect(x, 335, 18, 1, [191, 181, 150])
  for (const x of [38, 103, 251]) {
    rect(x, 328, 7, 1, [99, 104, 110])
    rect(x + 7, 329, 3, 1, [99, 104, 110])
    rect(x + 10, 330, 3, 1, [99, 104, 110])
  }
  rect(134, 299, 6, 4, [107, 111, 104])
  rect(135, 299, 4, 1, [170, 167, 151])
  rect(135, 301, 4, 1, [133, 137, 126])

  // Blend the sample block into the neutral ground beyond its paved area.
  for (let y = 196; y < height; y++) {
    for (let x = 0; x < 369; x++) {
      const amount = Math.min(1, (369 - x) / 39, (y - 196) / 9)
      if (amount === 1) continue
      const offset = (y * width + x) * 3
      for (let c = 0; c < 3; c++) data[offset + c] = Math.round(neutral[c] + (data[offset + c] - neutral[c]) * amount)
    }
  }
  return image
}

function worldRect(image, left, bottom, right, top, color, strength = 0) {
  const x = Math.round(left / 2)
  const y = image.height - Math.round(top * .3)
  const w = Math.round(right / 2) - x
  const h = image.height - Math.round(bottom * .3) - y
  if (strength) grain(image, x, y, w, h, color, strength)
  else image.rect(x, y, w, h, color)
}

function paintRoutes(image, routes, extra, color, strength = 0) {
  for (const route of routes) {
    const points = route.bake_start ? [route.bake_start, ...route.points.slice(1)] : route.points
    const half = route.width / 2 + extra
    for (let i = 1; i < points.length; i++) {
      const [ax, ay] = points[i - 1]
      const [bx, by] = points[i]
      const left = route.open_start && i === 1 ? ax : Math.min(ax, bx) - half
      worldRect(image, left, Math.min(ay, by) - half,
        Math.max(ax, bx) + half, Math.max(ay, by) + half, color, strength)
    }
  }
}

function ground() {
  const image = texture(1800, 720)
  const {rect, data, width, height} = image
  rect(0, 0, width, height, neutral)
  worldRect(image, 1715, 145, 3320, 2295, [116, 123, 108], 1)
  const old = southwestBlock()
  for (let row = 0; row < old.height; row++) {
    const rowBytes = old.width * 3
    old.data.copy(data, ((row + 360) * width) * 3, row * rowBytes, (row + 1) * rowBytes)
  }

  // Keep the original approach intact and start both road additions at its far edges.
  const {main, alleys} = roads
  const approaches = [
    {points: [[1958, 1000], [1958, 1041]], width: 40},
    {points: [[2280, 1720], [2280, 1760]], width: 42},
  ]
  paintRoutes(image, [...main, ...alleys], 21, [159, 155, 139], .8)
  paintRoutes(image, [...main, ...alleys], 4, [186, 177, 154])
  paintRoutes(image, main, 0, [109, 113, 117], 1.5)
  paintRoutes(image, alleys, 0, [128, 128, 118], 1.15)
  paintRoutes(image, approaches, 0, [156, 149, 134], 1.1)

  // Join the old horizontal dashes and turn them north past the corner.
  for (let x = 12 + 8 * 43; x < 1665; x += 43) rect(x, 695, 18, 1, [191, 181, 150])
  for (let y = 670; y > 58; y -= 26) rect(1690, y, 1, 11, [191, 181, 150])
  return image
}

function shop() {
  const image = house(130, 48, {
    roof: [101, 113, 112], wall: [143, 128, 109], trim: [188, 177, 149], door: [72, 95, 91], row: 6,
  }, 60, [])
  const {rect} = image
  grain(image, 1, 52, 128, 50, [138, 131, 115])
  // Petrol-green sign and striped canopy mark the shop from the road.
  rect(5, 53, 51, 11, [61, 90, 87])
  rect(5, 53, 51, 1, [116, 140, 129])
  const digits = ['110 101', '001 101', '111 111', '100 001', '111 001']
  digits.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      if (row[x] === '1') rect(25 + x * 2, 54 + y * 2, 2, 2, [222, 216, 171])
    }
  })
  rect(3, 65, 54, 6, [75, 118, 109])
  rect(83, 65, 44, 6, [75, 118, 109])
  for (const x of [5, 15, 25, 35, 45, 85, 95, 105, 115]) rect(x, 65, 4, 6, [178, 169, 137])
  rect(3, 71, 54, 1, [58, 75, 71])
  rect(83, 71, 44, 1, [58, 75, 71])
  windowFrame(image, 11, 77, 43, 18, [155, 166, 148])
  windowFrame(image, 80, 77, 39, 18, [155, 166, 148])
  door(image, 61, 56, 17, 46, [77, 104, 101], [157, 167, 147])
  rect(0, 102, 130, 1, [67, 75, 69])
  return image
}

function busStop() {
  const image = texture(70, 50)
  const {rect} = image
  grain(image, 0, 0, 70, 16, [102, 126, 131])
  for (let x = 9; x < 67; x += 10) rect(x, 1, 1, 13, [79, 103, 109])
  rect(0, 13, 70, 3, [145, 160, 149])
  grain(image, 0, 16, 70, 34, [83, 102, 108])
  rect(0, 17, 70, 3, [57, 77, 82])
  rect(6, 22, 58, 1, [127, 148, 148])
  rect(9, 29, 52, 1, [101, 128, 131])
  rect(5, 43, 60, 5, [69, 83, 84])
  for (const x of [1, 34, 66]) {
    rect(x, 19, 3, 30, [46, 69, 75])
    rect(x, 19, 1, 28, [116, 136, 136])
  }
  rect(9, 36, 29, 3, [153, 132, 99])
  rect(13, 39, 2, 7, [73, 80, 79])
  rect(32, 39, 2, 7, [73, 80, 79])
  rect(52, 24, 10, 13, [177, 183, 154])
  rect(54, 27, 6, 2, [63, 104, 110])
  rect(54, 32, 5, 1, [87, 107, 103])
  rect(0, 48, 70, 2, [58, 73, 77])
  return image
}

function streetlamp() {
  const image = texture(14, 54, 4)
  const {rect} = image
  rect(5, 8, 4, 45, [45, 59, 64, 255])
  rect(6, 8, 1, 43, [113, 126, 121, 255])
  rect(5, 6, 9, 3, [54, 71, 74, 255])
  rect(10, 3, 3, 4, [104, 118, 113, 255])
  rect(7, 1, 7, 3, [58, 76, 79, 255])
  rect(6, 3, 8, 2, [128, 139, 125, 255])
  rect(6, 5, 8, 2, [214, 177, 99, 255])
  rect(8, 6, 5, 2, [255, 228, 151, 255])
  rect(4, 50, 6, 3, [62, 77, 76, 255])
  rect(3, 53, 8, 1, [96, 108, 99, 255])
  return image
}

function windowFrame(image, x, y, w, h, trim) {
  const {rect} = image
  rect(x - 2, y - 2, w + 4, h + 4, [55, 55, 52])
  rect(x - 1, y - 1, w + 2, h + 2, trim)
  rect(x, y, w, h, [68, 83, 90])
  rect(x + 1, y + 1, w - 2, 4, [106, 129, 134])
  rect(x + Math.floor(w / 2), y, 1, h, trim)
  rect(x, y + Math.floor(h / 2), w, 1, trim)
  rect(x - 3, y + h, w + 6, 2, shade(trim, -16))
}

function door(image, x, y, w, h, color, trim) {
  const {rect} = image
  rect(x - 2, y - 2, w + 4, h + 2, [56, 49, 45])
  rect(x - 1, y - 1, w + 2, h + 1, trim)
  grain(image, x, y, w, h, color)
  rect(x + 2, y + 3, w - 4, 12, shade(color, -22))
  rect(x + 3, y + 4, w - 6, 9, shade(color, 11))
  rect(x + 3, y + 21, w - 6, h - 26, shade(color, -9))
  rect(x + w - 4, y + 23, 2, 2, [208, 174, 102])
  rect(x - 2, y + h - 1, w + 4, 2, shade(trim, -26))
}

function house(width, roofHeight, palette, doorX, windows) {
  const image = texture(width, roofHeight + 55)
  const {rect} = image
  grain(image, 0, 0, width, roofHeight, palette.roof)
  // Paired slopes, short roof tiles, and a raised ridge.
  grain(image, 0, 1, width, Math.floor(roofHeight * .40), shade(palette.roof, -18))
  for (let y = 3; y < roofHeight - 2; y += 5) {
    rect(1, y, width - 2, 1, shade(palette.roof, y < roofHeight * .4 ? -28 : -15))
    for (let x = 6 + (y % 2) * 4; x < width - 3; x += 10) {
      rect(x, y + 1, 1, Math.min(3, roofHeight - y - 2), shade(palette.roof, -10))
    }
  }
  const ridge = Math.floor(roofHeight * .40)
  rect(1, ridge, width - 2, 1, shade(palette.roof, 22))
  rect(1, ridge + 1, width - 2, 1, shade(palette.roof, 8))

  grain(image, 0, roofHeight, width, 55, palette.wall)
  for (let y = roofHeight + 6; y < image.height - 3; y += palette.row) {
    rect(1, y, width - 2, 1, shade(palette.wall, -13))
    if (palette.row === 6) {
      for (let x = (y % 4 ? 8 : 4); x < width - 3; x += 10) rect(x, y + 1, 1, 4, shade(palette.wall, -11))
    }
  }
  rect(0, roofHeight - 2, width, 2, shade(palette.roof, 15))
  rect(0, roofHeight, width, 2, shade(palette.trim, -15))
  rect(0, roofHeight + 2, width, 2, shade(palette.wall, -30))
  rect(0, image.height - 4, width, 4, shade(palette.wall, -30))
  rect(0, 0, 1, image.height, [66, 67, 67])
  rect(width - 1, 0, 1, image.height, [56, 58, 58])
  rect(0, 0, width, 1, [83, 83, 82])
  for (const x of windows) windowFrame(image, x, roofHeight + 18, 17, 20, palette.trim)
  door(image, doorX, roofHeight + 6, 17, 48, palette.door, palette.trim)
  return image
}

function fence() {
  const image = texture(50, 23)
  const {rect} = image
  grain(image, 0, 0, 50, 23, [133, 130, 116], 1.5)
  for (let y = 4; y < 21; y += 5) {
    rect(0, y, 50, 1, [105, 106, 96])
    for (let x = 5 + (y % 2) * 4; x < 49; x += 9) rect(x, y + 1, 1, 4, [108, 109, 99])
  }
  rect(0, 1, 50, 2, [170, 164, 141])
  rect(0, 3, 50, 1, [91, 94, 88])
  rect(0, 22, 50, 1, [85, 89, 83])
  for (const x of [0, 23, 46]) {
    rect(x, 0, 4, 23, [145, 140, 124])
    rect(x, 0, 4, 2, [180, 171, 145])
    rect(x + 3, 2, 1, 21, [104, 104, 94])
  }
  return image
}

async function save(name, image) {
  const file = path.join(output, name + '.png')
  const {data, width, height, channels} = image
  if (process.argv.includes('--check')) {
    const actual = await sharp(file).raw().toBuffer({resolveWithObject: true})
    assert.deepEqual([actual.info.width, actual.info.height, actual.info.channels], [width, height, channels])
    assert(actual.data.equals(data), name + ' differs from the bake')
  } else {
    await sharp(data, {raw: {width, height, channels}}).png().toFile(file)
  }
}

async function main() {
  await Promise.all([
    save('ground', ground()),
    save('west-house', house(70, 57, {
      roof: [112, 121, 130], wall: [172, 151, 121], trim: [205, 187, 153], door: [105, 122, 120], row: 7,
    }, 32, [8, 52])),
    save('east-house', house(138, 60, {
      roof: [129, 105, 98], wall: [160, 126, 111], trim: [190, 174, 150], door: [119, 91, 65], row: 6,
    }, 62, [13, 37, 96, 116])),
    save('fence', fence()),
    save('shop', shop()),
    save('bus-stop', busStop()),
    save('streetlamp', streetlamp()),
  ])
  console.log('Neighborhood textures verified')
}

main().catch(error => { console.error(error); process.exitCode = 1 })
