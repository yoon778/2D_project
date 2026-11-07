// Pixel-snapped upper-body weight shift, tapering into the fixed lower legs.
function shiftWeight(cell, size, offset, weight, fixedAbove, fixedBelow) {
  const [dx, dy] = weight
  const shifted = Buffer.alloc(cell.length)
  for (let y = 0; y < size; y++) {
    const taper = Math.max(0, Math.min(1, (fixedBelow - (y - offset)) / (fixedBelow - fixedAbove)))
    const sy = y - Math.round(dy * taper)
    const sx = Math.round(dx * taper)
    if (sy < 0 || sy >= size) continue
    const left = Math.max(0, sx)
    const right = Math.min(size, size + sx)
    cell.copy(shifted, (y * size + left) * 4, (sy * size + left - sx) * 4, (sy * size + right - sx) * 4)
  }
  return shifted
}

module.exports = {shiftWeight}
