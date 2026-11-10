// Dead Route neighborhood pixel textures. Bake with: node art/environment/bake-neighborhood.cjs
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

function weatherPaving(image) {
  const {width, height, data, point, rect} = image
  const original = Buffer.from(data)
  function material(x, y) {
    const offset = (y * width + x) * 3
    const r = original[offset], g = original[offset + 1], b = original[offset + 2]
    if (g - r === 4 && b - r === 8) return 'asphalt'
    if (g === r && r - b === 10) return 'alley'
    if (g - r === 7 && b < r - 7) return 'grass'
    return null
  }
  for (let y = 9; y < height - 9; y += 5) {
    for (let x = 9; x < width - 9; x += 7) {
      const noise = hash(x, y)
      const surface = material(x, y)
      if ((surface === 'asphalt' || surface === 'alley') && noise > 90) {
        const color = surface === 'asphalt' ? [92, 98, 103] : [111, 113, 103]
        const reach = 3 + noise % 4
        for (let dy = -2; dy <= 2; dy++) {
          for (let dx = -reach; dx <= reach; dx++) {
            if (Math.abs(dx) + Math.abs(dy) > reach + 1 || material(x + dx, y + dy) !== surface) continue
            if (hash(x + dx, y + dy) > 12) point(x + dx, y + dy, shade(color, hash(dx, dy) % 8))
          }
        }
      }
      if (surface === 'grass' && noise > 74 &&
          [material(x + 4, y), material(x - 4, y), material(x, y + 3), material(x, y - 3)].some(v => v !== 'grass')) {
        for (let dx = -3; dx <= 3; dx++) {
          if (material(x + dx, y) === 'grass') {
            point(x + dx, y, [78, 95, 72])
            point(x + dx, y - 1 - (hash(x + dx, y) % 2), [132, 144, 101])
          }
        }
      }
    }
  }
  for (const roadY of [535, 1000, 1720]) {
    const y = height - Math.round((roadY - 43) * .3)
    for (let x = 1674; x < 1708; x += 6) {
      rect(x, y, 3, 4, [175, 169, 146])
      point(x + 2, y + 3, [125, 129, 123])
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
  weatherPaving(image)
  return image
}

function line(image, x0, y0, x1, y1, color) {
  const dx = Math.abs(x1 - x0), sx = Math.sign(x1 - x0)
  const dy = -Math.abs(y1 - y0), sy = Math.sign(y1 - y0)
  let error = dx + dy
  while (true) {
    image.point(x0, y0, color)
    if (x0 === x1 && y0 === y1) return
    const doubled = 2 * error
    if (doubled >= dy) {
      error += dy
      x0 += sx
    }
    if (doubled <= dx) {
      error += dx
      y0 += sy
    }
  }
}

function vent(image, x, y, w, h) {
  const {rect} = image
  rect(x + 2, y + 2, w, h, [52, 60, 61])
  rect(x, y, w, h, [99, 112, 112])
  rect(x, y, w, 1, [146, 153, 143])
  rect(x, y + h - 2, w, 2, [72, 86, 87])
  for (let row = 3; row < h - 2; row += 2) rect(x + 2, y + row, w - 4, 1, [67, 79, 79])
}

function flatRoof(image, height, color) {
  const {rect, width} = image
  grain(image, 0, 0, width, height, shade(color, -18), .75)
  grain(image, 3, 3, width - 7, height - 6, color, 1.15)
  for (let x = 11; x < width - 6; x += 18) {
    rect(x, 4, 1, height - 8, shade(color, -10))
    rect(x + 1, 4, 1, height - 8, shade(color, 4))
  }
  rect(1, 1, width - 2, 2, shade(color, 19))
  rect(1, 3, 2, height - 6, shade(color, 8))
  rect(width - 4, 3, 2, height - 6, shade(color, -24))
  rect(1, height - 3, width - 2, 2, shade(color, 15))
  rect(0, height - 1, width, 1, shade(color, -39))
}

function brick(image, top, bottom, color) {
  const {width, rect} = image
  grain(image, 0, top, width, bottom - top, shade(color, -32))
  for (let y = top, row = 0; y < bottom; y += 5, row++) {
    for (let x = row % 2 === 0 ? 0 : -5; x < width; x += 11) {
      const tone = Math.floor(hash(x, y) / 7) - 7
      const h = Math.min(4, bottom - y)
      rect(x, y, 10, h, shade(color, tone))
      rect(x, y, 10, 1, shade(color, tone + 10))
    }
  }
}

function workshop() {
  const image = texture(100, 100)
  const {rect} = image
  flatRoof(image, 45, [96, 104, 100])
  vent(image, 10, 12, 15, 12)
  vent(image, 76, 24, 10, 8)
  rect(57, 10, 7, 7, [63, 69, 63])
  rect(56, 9, 7, 6, [127, 124, 104])
  rect(58, 10, 3, 3, [72, 75, 67])
  brick(image, 45, 99, [139, 111, 96])
  rect(0, 45, 100, 3, [81, 88, 83])
  rect(0, 99, 100, 1, [59, 63, 58])
  rect(8, 54, 56, 46, [67, 75, 73])
  rect(10, 55, 52, 43, [128, 137, 131])
  for (let y = 58; y < 97; y += 4) {
    rect(11, y, 50, 1, [91, 105, 103])
    rect(11, y + 1, 50, 1, [151, 155, 140])
  }
  rect(11, 91, 7, 5, [115, 97, 78])
  rect(55, 93, 6, 4, [119, 103, 83])
  rect(31, 94, 10, 1, [77, 86, 81])
  door(image, 75, 55, 16, 43, [81, 98, 95], [155, 144, 119])
  rect(72, 47, 22, 6, [74, 101, 94])
  rect(74, 48, 13, 1, [176, 183, 155])
  rect(74, 50, 17, 1, [150, 164, 149])
  return image
}


function shop() {
  const image = texture(130, 103)
  const {rect} = image
  flatRoof(image, 48, [102, 121, 113])
  vent(image, 20, 15, 17, 12)
  vent(image, 105, 27, 13, 10)
  rect(64, 12, 24, 14, [65, 81, 80])
  rect(65, 12, 22, 12, [139, 154, 143])
  rect(67, 14, 18, 8, [92, 122, 123])
  rect(75, 14, 1, 8, [136, 151, 140])
  brick(image, 48, 103, [145, 131, 113])
  rect(0, 48, 130, 3, [102, 123, 109])
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
  rect(0, 0, 70, 2, [80, 98, 103])
  rect(0, 10, 70, 3, [110, 132, 135])
  rect(0, 13, 70, 3, [160, 172, 159])
  grain(image, 0, 16, 70, 34, [83, 102, 108])
  rect(0, 17, 70, 3, [57, 77, 82])
  line(image, 7, 32, 21, 23, [125, 148, 146])
  line(image, 8, 35, 28, 22, [112, 136, 138])
  line(image, 36, 34, 51, 25, [115, 138, 140])
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
  rect(54, 34, 6, 1, [103, 122, 111])
  rect(54, 36, 4, 1, [103, 122, 111])
  rect(45, 43, 6, 4, [72, 99, 99])
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

function gabledRoof(image, height, color, tile) {
  const {width, point, rect} = image
  const ridgeY = Math.floor(height * .39)
  const hipWidth = Math.min(18, Math.floor(width * .19))
  const tileHeight = tile === 'clay' ? 5 : 4
  const tileWidth = tile === 'clay' ? 7 : 9
  for (let y = 0; y < height; y++) {
    const rise = y <= ridgeY ? y / ridgeY : (height - y - 1) / (height - ridgeY - 1)
    const hip = Math.floor(rise * hipWidth)
    for (let x = 0; x < width; x++) {
      const plane = x < hip ? -8 : x >= width - hip ? -31 : y <= ridgeY ? -23 : 3
      const course = Math.floor(y / tileHeight)
      const stagger = course % 2 === 0 ? 0 : Math.floor(tileWidth / 2)
      const joint = (x + stagger) % tileWidth === 0
      const edge = y % tileHeight
      const relief = edge === tileHeight - 1 ? -17 : edge === 0 ? 9 : joint ? -9 : 0
      const patch = Math.floor(hash(Math.floor(x / tileWidth), course) / 9) - 5
      point(x, y, shade(color, plane + relief + patch))
    }
  }
  const seam = shade(color, 18)
  line(image, 0, 1, hipWidth, ridgeY, seam)
  line(image, hipWidth, ridgeY, 0, height - 2, shade(color, 9))
  line(image, width - 1, 1, width - hipWidth - 1, ridgeY, shade(color, -4))
  line(image, width - hipWidth - 1, ridgeY, width - 1, height - 2, shade(color, -13))
  rect(hipWidth, ridgeY, width - 2 * hipWidth, 2, seam)
  rect(hipWidth, ridgeY + 2, width - 2 * hipWidth, 1, shade(color, -18))
  rect(0, height - 2, width, 1, shade(color, 15))
  rect(0, height - 1, width, 1, shade(color, -28))
}

function chimney(image, x, y, color) {
  const {rect} = image
  rect(x + 2, y + 3, 8, 9, [63, 65, 60])
  rect(x, y + 2, 8, 9, color)
  rect(x + 6, y + 2, 2, 9, shade(color, -21))
  rect(x, y + 6, 8, 1, shade(color, -18))
  rect(x - 1, y, 10, 3, shade(color, 21))
  rect(x + 1, y + 1, 6, 1, [77, 78, 71])
}

function house(width, roofHeight, palette, doorX, windows) {
  const image = texture(width, roofHeight + 55)
  const {rect, height} = image
  gabledRoof(image, roofHeight, palette.roof, palette.tile)
  chimney(image, width - 27, Math.floor(roofHeight * .27), palette.chimney)

  if (palette.tile === 'clay') {
    brick(image, roofHeight, height, palette.wall)
  } else {
    grain(image, 0, roofHeight, width, 55, palette.wall)
    for (let y = roofHeight + 5; y < height - 2; y += 5) {
      rect(0, y, width, 1, shade(palette.wall, -22))
      rect(0, y + 1, width, 1, shade(palette.wall, 12))
    }
  }
  rect(0, roofHeight, width, 2, shade(palette.trim, -6))
  rect(0, roofHeight + 2, width, 3, shade(palette.wall, -37))
  rect(0, height - 5, width, 5, [111, 113, 103])
  rect(0, height - 5, width, 1, [144, 142, 127])
  rect(1, roofHeight + 5, 2, 44, shade(palette.trim, -25))
  rect(width - 3, roofHeight + 5, 2, 44, shade(palette.wall, -23))
  rect(0, 0, 1, height, [72, 75, 72])
  rect(width - 1, 0, 1, height, [53, 57, 57])
  rect(0, 0, width, 1, [107, 111, 106])
  for (const x of windows) windowFrame(image, x, roofHeight + 19, palette.windowWidth, 20, palette.trim)
  door(image, doorX, roofHeight + 6, 17, 47, palette.door, palette.trim)
  rect(doorX - 3, height - 2, 23, 1, [174, 170, 147])
  rect(doorX - 4, height - 1, 25, 1, [112, 113, 103])
  return image
}


function houseSide(wall, trim, masonry) {
  const image = texture(56, 55)
  const {width, rect} = image
  if (masonry) {
    brick(image, 0, 55, wall)
  } else {
    grain(image, 0, 0, width, 55, wall)
    for (let y = 5; y < 50; y += 5) {
      rect(0, y, width, 1, shade(wall, -22))
      rect(0, y + 1, width, 1, shade(wall, 10))
    }
  }
  rect(0, 0, width, 2, shade(trim, -14))
  rect(0, 2, width, 3, shade(wall, -31))
  rect(0, 50, width, 5, [93, 98, 89])
  rect(0, 50, width, 1, [126, 125, 110])
  rect(0, 3, 1, 47, shade(trim, -34))
  rect(width - 2, 4, 2, 46, shade(wall, -25))
  windowFrame(image, 28, 18, 12, 15, shade(trim, -13))
  if (masonry) {
    rect(46, 5, 2, 43, [84, 87, 80])
    rect(45, 5, 1, 42, [134, 132, 114])
    rect(43, 47, 5, 2, [79, 85, 79])
  } else {
    rect(7, 30, 6, 7, [96, 105, 97])
    rect(8, 30, 4, 2, [155, 162, 147])
    rect(11, 37, 1, 11, [108, 114, 105])
  }
  return image
}


function fence() {
  const image = texture(50, 23)
  const {rect} = image
  grain(image, 0, 0, 50, 23, [133, 130, 116], 1.5)
  for (let y = 4; y < 21; y += 5) {
    rect(0, y, 50, 1, [105, 106, 96])
    for (let x = 5 + (y % 2) * 4; x < 49; x += 9) {
      rect(x, y + 1, 1, 4, [108, 109, 99])
      rect(x + 1, y + 1, 6, 1, [155, 148, 130])
    }
  }
  rect(0, 1, 50, 2, [170, 164, 141])
  rect(0, 3, 50, 1, [91, 94, 88])
  rect(0, 22, 50, 1, [85, 89, 83])
  for (const [x, w] of [[4, 6], [14, 4], [29, 8], [42, 4]]) {
    rect(x, 21, w, 1, [99, 111, 88])
    rect(x + 2, 20, 2, 1, [109, 122, 95])
  }
  for (const x of [0, 23, 46]) {
    rect(x, 0, 4, 23, [145, 140, 124])
    rect(x, 0, 4, 2, [180, 171, 145])
    rect(x + 3, 2, 1, 21, [104, 104, 94])
  }
  return image
}

function parkedCar() {
  const image = texture(56, 31)
  const {rect} = image
  rect(0, 0, 56, 31, [29, 35, 38])
  rect(2, 11, 51, 15, [79, 56, 49])
  rect(4, 9, 12, 4, [143, 91, 73])
  rect(12, 5, 31, 9, [131, 91, 75])
  rect(15, 3, 25, 8, [170, 109, 84])
  rect(17, 2, 22, 2, [187, 128, 98])
  rect(10, 8, 8, 5, [79, 103, 108])
  rect(14, 7, 6, 4, [105, 123, 123])
  rect(37, 6, 6, 7, [69, 96, 104])
  rect(39, 8, 6, 5, [104, 128, 130])
  rect(43, 10, 9, 5, [160, 101, 77])
  rect(48, 12, 6, 4, [183, 117, 88])
  rect(3, 13, 51, 10, [148, 83, 66])
  rect(3, 20, 51, 2, [117, 72, 61])
  rect(4, 22, 48, 3, [104, 62, 54])
  rect(6, 15, 44, 1, [182, 111, 83])
  rect(16, 11, 23, 6, [67, 88, 94])
  rect(17, 11, 20, 1, [132, 149, 145])
  rect(26, 11, 2, 12, [86, 62, 56])
  rect(37, 12, 2, 10, [86, 62, 56])
  rect(22, 18, 3, 1, [199, 158, 123])
  rect(33, 18, 3, 1, [199, 158, 123])
  rect(3, 18, 4, 2, [190, 97, 75])
  rect(49, 17, 5, 2, [226, 198, 132])
  rect(1, 23, 8, 3, [96, 102, 100])
  rect(49, 23, 6, 3, [117, 118, 108])
  rect(17, 26, 22, 2, [44, 49, 49])
  for (const x of [9, 39]) {
    rect(x + 1, 21, 8, 9, [33, 37, 40])
    rect(x, 23, 10, 5, [33, 37, 40])
    rect(x + 2, 22, 6, 1, [59, 64, 65])
    rect(x + 3, 24, 4, 4, [96, 105, 105])
    rect(x + 4, 25, 2, 2, [144, 148, 136])
  }
  return image
}

function dumpster() {
  const image = texture(30, 24)
  const {rect} = image
  rect(0, 0, 30, 24, [34, 46, 44])
  grain(image, 2, 10, 26, 12, [81, 109, 94])
  rect(2, 2, 26, 8, [105, 120, 108])
  rect(3, 1, 24, 2, [132, 145, 123])
  rect(2, 8, 26, 3, [68, 87, 77])
  rect(3, 8, 24, 1, [144, 152, 124])
  rect(14, 2, 1, 6, [74, 92, 84])
  for (const x of [5, 10, 18, 23]) {
    rect(x, 4, 1, 3, [83, 101, 91])
    rect(x, 12, 1, 9, [58, 88, 75])
  }
  rect(9, 13, 10, 4, [172, 163, 110])
  rect(11, 14, 6, 1, [105, 101, 77])
  rect(4, 19, 4, 1, [129, 113, 83])
  rect(21, 18, 4, 1, [123, 111, 87])
  rect(3, 21, 24, 1, [62, 83, 72])
  rect(4, 22, 4, 2, [39, 42, 43])
  rect(22, 22, 4, 2, [39, 42, 43])
  return image
}


function mailbox() {
  const image = texture(10, 24, 4)
  const {rect} = image
  rect(4, 8, 3, 16, [73, 67, 57, 255])
  rect(4, 9, 1, 14, [130, 118, 95, 255])
  rect(2, 4, 8, 7, [64, 80, 80, 255])
  rect(2, 3, 7, 2, [133, 146, 134, 255])
  rect(1, 5, 8, 4, [109, 124, 116, 255])
  rect(2, 9, 7, 1, [84, 99, 93, 255])
  rect(8, 5, 1, 5, [57, 70, 69, 255])
  rect(6, 1, 1, 6, [183, 91, 72, 255])
  rect(6, 1, 3, 2, [206, 108, 85, 255])
  return image
}

function planter() {
  const image = texture(13, 15, 4)
  const {rect} = image
  rect(1, 4, 11, 5, [60, 81, 66, 255])
  rect(3, 2, 7, 5, [77, 103, 77, 255])
  rect(5, 0, 3, 5, [106, 128, 88, 255])
  rect(2, 5, 3, 2, [110, 131, 92, 255])
  rect(7, 3, 3, 2, [138, 148, 104, 255])
  rect(8, 5, 3, 2, [95, 119, 80, 255])
  rect(1, 8, 11, 3, [132, 87, 70, 255])
  rect(2, 8, 9, 1, [183, 127, 95, 255])
  rect(2, 11, 9, 3, [141, 91, 73, 255])
  rect(3, 11, 2, 2, [160, 104, 81, 255])
  rect(3, 14, 7, 1, [83, 62, 57, 255])
  return image
}

function bicycle() {
  const image = texture(23, 16, 4)
  const {rect, point} = image
  const tire = [47, 55, 57, 255]
  const metal = [141, 150, 139, 255]
  const frame = [173, 111, 81, 255]
  for (const x of [1, 14]) {
    rect(x + 2, 7, 5, 1, tire)
    rect(x + 2, 15, 5, 1, tire)
    rect(x, 9, 1, 5, tire)
    rect(x + 8, 9, 1, 5, tire)
    for (const y of [8, 14]) {
      point(x + 1, y, metal)
      point(x + 7, y, metal)
    }
    point(x + 4, 11, metal)
    line(image, x + 2, 9, x + 6, 13, [86, 99, 95, 255])
  }
  line(image, 5, 11, 9, 5, frame)
  line(image, 9, 5, 12, 11, frame)
  line(image, 12, 11, 5, 11, frame)
  line(image, 12, 11, 16, 5, frame)
  line(image, 9, 5, 16, 5, frame)
  line(image, 16, 5, 18, 11, metal)
  line(image, 16, 5, 15, 2, metal)
  rect(15, 1, 4, 1, metal)
  rect(7, 3, 5, 1, tire)
  point(12, 11, [215, 173, 118, 255])
  return image
}

function trashBags() {
  const image = texture(15, 12, 4)
  const {rect} = image
  rect(6, 4, 9, 7, [57, 72, 71, 255])
  rect(8, 2, 5, 4, [73, 87, 84, 255])
  rect(9, 0, 3, 2, [91, 106, 98, 255])
  rect(9, 3, 3, 1, [116, 126, 112, 255])
  rect(1, 6, 9, 5, [44, 56, 56, 255])
  rect(2, 4, 6, 3, [66, 81, 79, 255])
  rect(4, 2, 3, 2, [100, 111, 102, 255])
  rect(2, 7, 3, 1, [83, 97, 91, 255])
  rect(5, 8, 3, 1, [64, 76, 73, 255])
  rect(12, 6, 2, 2, [84, 98, 91, 255])
  rect(2, 11, 11, 1, [38, 48, 48, 255])
  return image
}

function metalBin() {
  const image = texture(13, 21, 4)
  const {rect} = image
  rect(2, 5, 9, 15, [113, 125, 122, 255])
  rect(3, 8, 2, 11, [147, 154, 142, 255])
  rect(6, 8, 1, 11, [92, 110, 109, 255])
  rect(9, 8, 1, 11, [76, 96, 96, 255])
  rect(2, 17, 9, 1, [95, 109, 108, 255])
  rect(3, 20, 7, 1, [64, 79, 80, 255])
  rect(1, 4, 11, 3, [143, 152, 143, 255])
  rect(2, 3, 9, 1, [177, 180, 158, 255])
  rect(1, 6, 11, 1, [81, 101, 101, 255])
  rect(5, 1, 4, 2, [89, 108, 106, 255])
  return image
}

function recyclingBin() {
  const image = texture(14, 22, 4)
  const {rect} = image
  rect(2, 6, 10, 14, [66, 110, 113, 255])
  rect(3, 7, 2, 12, [89, 131, 128, 255])
  rect(10, 7, 2, 12, [46, 86, 90, 255])
  rect(1, 3, 12, 4, [80, 126, 128, 255])
  rect(2, 2, 10, 2, [112, 151, 143, 255])
  rect(1, 6, 12, 1, [48, 81, 85, 255])
  rect(3, 20, 9, 2, [49, 60, 63, 255])
  rect(3, 20, 2, 1, [94, 105, 103, 255])
  const mark = [171, 187, 152, 255]
  line(image, 5, 13, 7, 10, mark)
  line(image, 7, 10, 9, 13, mark)
  rect(5, 14, 5, 1, mark)
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
      roof: [111, 126, 138], wall: [156, 163, 144], trim: [204, 193, 162],
      door: [89, 115, 105], chimney: [152, 135, 113], tile: 'slate', windowWidth: 14,
    }, 32, [8, 52])),
    save('east-house', house(138, 60, {
      roof: [145, 109, 98], wall: [157, 126, 110], trim: [195, 179, 152],
      door: [111, 90, 69], chimney: [159, 125, 106], tile: 'clay', windowWidth: 17,
    }, 62, [13, 37, 96, 116])),
    save('west-house-side', houseSide([138, 146, 128], [204, 193, 162], false)),
    save('east-house-side', houseSide([142, 113, 100], [195, 179, 152], true)),
    save('fence', fence()),
    save('shop', shop()),
    save('workshop', workshop()),
    save('bus-stop', busStop()),
    save('streetlamp', streetlamp()),
    save('parked-car', parkedCar()),
    save('dumpster', dumpster()),
    save('mailbox', mailbox()),
    save('planter', planter()),
    save('bicycle', bicycle()),
    save('trash-bags', trashBags()),
    save('metal-bin', metalBin()),
    save('recycling-bin', recyclingBin()),
  ])
  console.log('Neighborhood textures verified')
}

main().catch(error => { console.error(error); process.exitCode = 1 })
