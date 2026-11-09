// Pixel runs on each 80 px master. A run clears the old parcel, then paints
// the jacket underneath. Uncovered hands, straps and the bat stay in place.
const shade = Buffer.from([39, 42, 57, 255])
const cloth = Buffer.from([51, 55, 72, 255])
const ink = Buffer.from([25, 24, 31, 255])
const cuts = {
  front_right: [
    [36, 45, 53, 45, 53], [37, 44, 54, 44, 54], [38, 43, 54, 43, 54],
    [39, 43, 54, 43, 54], [40, 43, 54, 43, 54], [41, 43, 54, 43, 54],
    [42, 43, 53, 43, 53], [43, 43, 51, 43, 51], [44, 43, 50, 43, 50],
    [45, 45, 51, 45, 51], [46, 46, 48, 46, 48],
  ],
  front_left: [
    [36, 36, 46, 36, 46], [37, 36, 47, 36, 47], [38, 36, 47, 36, 47],
    [39, 36, 47, 36, 47], [40, 36, 47, 36, 47], [41, 36, 47, 36, 47],
    [42, 36, 45, 36, 45], [43, 36, 42, 36, 42], [44, 36, 41, 36, 41],
    [45, 36, 42, 36, 42], [46, 37, 39, 37, 39],
  ],
  front: [
    [36, 44, 51, 44, 51], [37, 43, 52, 43, 52], [38, 42, 52, 42, 52],
    [39, 42, 52, 42, 52], [40, 42, 52, 42, 52], [41, 42, 52, 42, 52],
    [42, 42, 52, 42, 52], [43, 42, 49, 42, 49], [44, 42, 48, 42, 48],
    [45, 43, 49, 43, 49], [46, 44, 47, 44, 47],
  ],
  back_left: [
    [34, 24, 27, 27, 27], [35, 24, 27, 27, 27], [36, 24, 26, 26, 26],
    [37, 24, 26, 26, 26], [38, 24, 25, 25, 25], [39, 24, 25, 25, 25],
  ],
  left: [
    [35, 29, 38, 33, 38], [36, 28, 39, 32, 39], [37, 27, 39, 32, 39],
    [38, 28, 39, 32, 39], [39, 28, 39, 32, 39], [40, 28, 39, 32, 39],
    [41, 28, 38, 31, 38], [42, 28, 35, 31, 35], [43, 28, 31, 31, 31],
    [44, 28, 31, 31, 31], [45, 28, 30, 31, 30],
  ],
  right: [
    [34, 49, 52, 49, 49], [35, 49, 53, 49, 49], [36, 48, 54, 48, 49],
    [37, 48, 55, 48, 49], [38, 48, 55, 48, 49], [39, 48, 55, 48, 49],
    [40, 48, 55, 48, 49], [41, 47, 55, 47, 49], [42, 47, 55, 47, 49],
    [43, 47, 55, 47, 49], [44, 47, 54, 47, 49], [45, 47, 52, 47, 48],
    [46, 48, 52, 48, 48],
  ],
}

function removeParcel(facing, pixels, width, left = 0, top = 0) {
  const runs = cuts[facing] || []
  for (const [y, first, last, fillFrom, fillTo] of runs) {
    const offset = ((top + y) * width + left) * 4
    pixels.fill(0, offset + first * 4, offset + (last + 1) * 4)
    for (let x = fillFrom; x <= fillTo; x++) {
      const exposed = x === fillFrom && fillFrom > first || x === fillTo && fillTo < last
      const color = exposed ? ink : (y >= 43 ? shade : cloth)
      color.copy(pixels, offset + x * 4)
    }
  }
  return pixels
}

function removeWalkParcels(facing, atlas, bodyDrop) {
  const result = Buffer.from(atlas)
  for (let frame = 0; frame <= bodyDrop.length; frame++) {
    removeParcel(facing, result, 320, frame % 4 * 80, Math.floor(frame / 4) * 80 + (bodyDrop[frame] || 0))
  }
  return result
}

module.exports = {removeParcel, removeWalkParcels}
