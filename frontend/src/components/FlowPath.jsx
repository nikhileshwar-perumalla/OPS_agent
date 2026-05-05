import React, { useMemo } from 'react';

let _id = 0;
const nextId = () => `fp${++_id}`;

export function FlowPath({
  d,
  packets = 2,
  dur = 1.8,
  color = 'var(--blue)',
  dash = false,
  strokeWidth = 1.4,
  stroke = 'var(--line-2)',
}) {
  const id = useMemo(nextId, []);
  return (
    <g>
      <path
        id={id}
        d={d}
        stroke={stroke}
        strokeWidth={strokeWidth}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={dash ? '5 5' : undefined}
      />
      {Array.from({ length: packets }).map((_, i) => (
        <circle key={i} r={3.2} fill={color} stroke="rgba(0,0,0,0.15)" strokeWidth={0.5}>
          <animateMotion
            dur={`${dur}s`}
            repeatCount="indefinite"
            begin={`${(i * dur) / packets}s`}
          >
            <mpath href={`#${id}`} />
          </animateMotion>
        </circle>
      ))}
    </g>
  );
}

export function ArrowHead({ x, y, color = 'var(--line-2)' }) {
  return (
    <path
      d={`M ${x - 6} ${y - 4} L ${x} ${y} L ${x - 6} ${y + 4}`}
      stroke={color}
      strokeWidth="1.4"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  );
}
