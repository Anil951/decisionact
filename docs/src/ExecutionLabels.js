const labelHeight = 28;

function overlaps(a, b, gap = 6) {
  return a.x < b.x + b.width + gap && a.x + a.width > b.x - gap
    && a.y < b.y + b.height + gap && a.y + a.height > b.y - gap;
}

function segmentHitsBox(a, b, box, gap = 3) {
  const left = box.x - gap, right = box.x + box.width + gap;
  const top = box.y - gap, bottom = box.y + box.height + gap;
  if (Math.abs(a[1] - b[1]) < .01) {
    return a[1] >= top && a[1] <= bottom && Math.max(a[0], b[0]) >= left && Math.min(a[0], b[0]) <= right;
  }
  return a[0] >= left && a[0] <= right && Math.max(a[1], b[1]) >= top && Math.min(a[1], b[1]) <= bottom;
}

function segmentsOf(edge) {
  let travelled = 0;
  return edge.points.slice(1).flatMap((b, index) => {
    const a = edge.points[index];
    const length = Math.abs(b[0] - a[0]) + Math.abs(b[1] - a[1]);
    const segment = {id:edge.id,a,b,length,travelled,horizontal:Math.abs(a[1] - b[1]) < .01};
    travelled += length;
    return length > 1 ? [segment] : [];
  });
}

// Labels belong to an actual segment, never to a free-floating position near it.
export function attachLabelsToEdges(edges, nodes, headings = []) {
  const obstacles = [...nodes, ...headings];
  const placedLabels = [];
  const placedPointers = [];
  const allSegments = edges.flatMap(segmentsOf);

  return edges.map(edge => {
    if (!edge.label) return edge;
    const width = edge.label.length * 7.3 + 20;
    const halfWidth = width / 2, halfHeight = labelHeight / 2;
    const others = allSegments.filter(segment => segment.id !== edge.id);
    const aboveOrigin = edge.labelSide === 'above';
    let best;

    function consider(anchor, centre, travelled, inline = false, horizontal = false) {
      if (aboveOrigin && (!horizontal || inline || centre[1] >= anchor[1] || anchor[1] !== edge.points[0][1])) return;
      const box = {x:centre[0] - halfWidth,y:centre[1] - halfHeight,width,height:labelHeight};
      if (box.x < -60 || box.x + width > 1580 || box.y < 0) return;
      if ([...obstacles,...placedLabels].some(obstacle => overlaps(box, obstacle))) return;

      let pointer;
      if (!inline) {
        // A short normal to the arrow ends at the nearest edge of its label.
        const end = horizontal
          ? [anchor[0],centre[1] + (anchor[1] < centre[1] ? -halfHeight : halfHeight)]
          : [centre[0] + (anchor[0] < centre[0] ? -halfWidth : halfWidth),anchor[1]];
        pointer = [anchor,end];
        if ([...obstacles,...placedLabels].some(obstacle => segmentHitsBox(anchor,end,obstacle))) return;
      }

      // Prefer a clear segment close to the branch origin. In crowded gutters,
      // use another part of this same arrow rather than cover a neighbouring one.
      const crossings = others.filter(segment => segmentHitsBox(segment.a,segment.b,box)).length;
      const pointerConflicts = placedPointers.filter(([a,b]) => segmentHitsBox(a,b,box)).length;
      const pointerBox = pointer && {
        x:Math.min(pointer[0][0],pointer[1][0]),y:Math.min(pointer[0][1],pointer[1][1]),
        width:Math.abs(pointer[0][0] - pointer[1][0]),height:Math.abs(pointer[0][1] - pointer[1][1]),
      };
      const pointerCrossings = pointerBox ? others.filter(segment => segmentHitsBox(segment.a,segment.b,pointerBox,1)).length : 0;
      const pointerLength = pointer ? Math.abs(pointer[0][0] - pointer[1][0]) + Math.abs(pointer[0][1] - pointer[1][1]) : 0;
      const score = (crossings + pointerConflicts + pointerCrossings) * 1000 + travelled * .15 + pointerLength * .5 + (inline ? 0 : 18);
      if (!best || score < best.score) best = {score,box,centre,anchor,pointer};
    }

    for (const segment of segmentsOf(edge)) {
      const {a,b,length,horizontal,travelled} = segment;
      const offsets = new Set([length / 2]);
      for (let distance = 24; distance < length - 16; distance += 48) offsets.add(distance);
      if (horizontal && length >= width + 32) {
        offsets.add(halfWidth + 16);
        offsets.add(length - halfWidth - 16);
      }
      for (const distance of [...offsets].sort((left,right) => left - right)) {
        const fraction = distance / length;
        const anchor = [a[0] + (b[0] - a[0]) * fraction,a[1] + (b[1] - a[1]) * fraction];
        if (horizontal) {
          if (distance >= halfWidth + 16 && length - distance >= halfWidth + 16) {
            consider(anchor,anchor,travelled + distance,true,true);
          }
          for (const gap of aboveOrigin ? [12,28,48,72] : [12,28,48]) {
            for (const side of [-1,1]) {
              for (const shift of aboveOrigin ? [0,-halfWidth / 2,halfWidth / 2,halfWidth - 12] : [0,-halfWidth / 2,halfWidth / 2]) {
                consider(anchor,[anchor[0] + shift,anchor[1] + side * (halfHeight + gap)],travelled + distance,false,true);
              }
            }
          }
        } else {
          for (const gap of [12,28,48]) {
            for (const side of [1,-1]) {
              consider(anchor,[anchor[0] + side * (halfWidth + gap),anchor[1]],travelled + distance);
            }
          }
        }
      }
    }

    if (!best) {
      // Retain an explicit pointer even if a future diagram has no open gutter.
      const centre = edge.labelAt || edge.points[0];
      const nearest = segmentsOf(edge).map(segment => {
        const {a,b,horizontal} = segment;
        const anchor = horizontal
          ? [Math.max(Math.min(a[0],b[0]),Math.min(Math.max(a[0],b[0]),centre[0])),a[1]]
          : [a[0],Math.max(Math.min(a[1],b[1]),Math.min(Math.max(a[1],b[1]),centre[1]))];
        return {anchor,horizontal,distance:Math.abs(anchor[0] - centre[0]) + Math.abs(anchor[1] - centre[1])};
      }).sort((a,b) => a.distance - b.distance)[0];
      const end = nearest.horizontal
        ? [nearest.anchor[0],centre[1] + (nearest.anchor[1] < centre[1] ? -halfHeight : halfHeight)]
        : [centre[0] + (nearest.anchor[0] < centre[0] ? -halfWidth : halfWidth),nearest.anchor[1]];
      best = {centre,anchor:nearest.anchor,pointer:[nearest.anchor,end],box:{x:centre[0] - halfWidth,y:centre[1] - halfHeight,width,height:labelHeight}};
    }
    placedLabels.push(best.box);
    if (best.pointer) placedPointers.push(best.pointer);
    return {...edge,labelAt:best.centre,labelWidth:width,labelHeight,labelAnchor:best.anchor,labelPointer:best.pointer};
  });
}
