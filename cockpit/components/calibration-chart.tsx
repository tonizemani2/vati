"use client";

// Calibration plot: predicted probability (x) vs realized frequency (y).
// A perfectly-calibrated forecaster sits on the diagonal. Empty until forecasts resolve.
import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
} from "recharts";

export type CalPoint = { predicted: number; realized: number };

export function CalibrationChart({ points }: { points: CalPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
        No resolved forecasts yet — the calibration curve appears once cards resolve.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={192}>
      <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          type="number"
          dataKey="predicted"
          domain={[0, 1]}
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => `${Math.round(v * 100)}%`}
        />
        <YAxis
          type="number"
          dataKey="realized"
          domain={[0, 1]}
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => `${Math.round(v * 100)}%`}
        />
        <ReferenceLine
          segment={[
            { x: 0, y: 0 },
            { x: 1, y: 1 },
          ]}
          stroke="currentColor"
          strokeDasharray="4 4"
          className="text-muted-foreground"
        />
        <Scatter data={points} fill="currentColor" className="text-primary" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
