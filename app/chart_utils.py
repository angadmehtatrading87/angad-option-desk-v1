def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def svg_line_chart(values, width=900, height=220, stroke="#63a4ff"):
    vals = [_safe_float(v) for v in values if v is not None]
    if len(vals) < 2:
        return '<div style="color:#91a4c4;font-size:13px;">Waiting for fresh data…</div>'

    min_v = min(vals)
    max_v = max(vals)
    rng = max(max_v - min_v, 1e-9)

    pts = []
    for i, v in enumerate(vals):
        x = 20 + (i * (width - 40) / max(len(vals) - 1, 1))
        y = 20 + ((max_v - v) / rng) * (height - 40)
        pts.append((x, y))

    line_points = " ".join([f"{x:.1f},{y:.1f}" for x, y in pts])
    area_points = f"20,{height-20} " + line_points + f" {width-20},{height-20}"

    start_v = vals[0]
    end_v = vals[-1]
    delta = end_v - start_v
    delta_color = "#25c27a" if delta >= 0 else "#ff6b6b"

    return f'''
    <svg viewBox="0 0 {width} {height}" width="100%" height="{height}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="grad1" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="{stroke}" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="{stroke}" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <line x1="20" y1="{height-20}" x2="{width-20}" y2="{height-20}" stroke="#22314d" stroke-width="1"/>
      <line x1="20" y1="20" x2="20" y2="{height-20}" stroke="#22314d" stroke-width="1"/>
      <polygon points="{area_points}" fill="url(#grad1)"/>
      <polyline points="{line_points}" fill="none" stroke="{stroke}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      <text x="28" y="18" fill="#91a4c4" font-size="11">start {start_v:,.2f}</text>
      <text x="170" y="18" fill="{delta_color}" font-size="11">delta {delta:,.2f}</text>
      <text x="{width-160}" y="18" fill="#91a4c4" font-size="11">latest {end_v:,.2f}</text>
    </svg>
    '''

def svg_dual_line_chart(values_a, values_b, width=900, height=220, stroke_a="#63a4ff", stroke_b="#25c27a"):
    a = [_safe_float(v) for v in values_a if v is not None]
    b = [_safe_float(v) for v in values_b if v is not None]
    n = min(len(a), len(b))
    if n < 2:
        return '<div style="color:#91a4c4;font-size:13px;">Waiting for fresh data…</div>'
    a = a[-n:]
    b = b[-n:]
    all_vals = a + b
    min_v = min(all_vals)
    max_v = max(all_vals)
    rng = max(max_v - min_v, 1e-9)

    def pts(vals):
        out = []
        for i, v in enumerate(vals):
            x = 20 + (i * (width - 40) / max(len(vals) - 1, 1))
            y = 20 + ((max_v - v) / rng) * (height - 40)
            out.append((x, y))
        return out

    pa = pts(a)
    pb = pts(b)
    line_a = " ".join([f"{x:.1f},{y:.1f}" for x, y in pa])
    line_b = " ".join([f"{x:.1f},{y:.1f}" for x, y in pb])

    return f'''
    <svg viewBox="0 0 {width} {height}" width="100%" height="{height}" preserveAspectRatio="none">
      <line x1="20" y1="{height-20}" x2="{width-20}" y2="{height-20}" stroke="#22314d" stroke-width="1"/>
      <line x1="20" y1="20" x2="20" y2="{height-20}" stroke="#22314d" stroke-width="1"/>
      <polyline points="{line_a}" fill="none" stroke="{stroke_a}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      <polyline points="{line_b}" fill="none" stroke="{stroke_b}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      <text x="28" y="18" fill="{stroke_a}" font-size="11">cash</text>
      <text x="82" y="18" fill="{stroke_b}" font-size="11">equity</text>
    </svg>
    '''

def svg_bar_chart(values_pos, values_neg, width=900, height=220):
    pos = [_safe_float(v) for v in values_pos]
    neg = [_safe_float(v) for v in values_neg]
    n = min(len(pos), len(neg))
    if n < 1:
        return '<div style="color:#91a4c4;font-size:13px;">Waiting for fresh data…</div>'
    pos = pos[-n:]
    neg = neg[-n:]
    all_vals = pos + neg + [0]
    max_abs = max(abs(v) for v in all_vals) or 1
    baseline = height / 2
    bar_w = max((width - 60) / max(n * 2, 1), 6)

    rects = []
    for i in range(n):
        x_base = 30 + i * ((width - 60) / max(n, 1))
        p = pos[i]
        nh = (abs(neg[i]) / max_abs) * (height/2 - 30)
        ph = (abs(p) / max_abs) * (height/2 - 30)
        rects.append(f'<rect x="{x_base:.1f}" y="{baseline-ph:.1f}" width="{bar_w:.1f}" height="{ph:.1f}" rx="3" fill="#25c27a"/>')
        rects.append(f'<rect x="{x_base+bar_w+3:.1f}" y="{baseline:.1f}" width="{bar_w:.1f}" height="{nh:.1f}" rx="3" fill="#ff6b6b"/>')

    return f'''
    <svg viewBox="0 0 {width} {height}" width="100%" height="{height}" preserveAspectRatio="none">
      <line x1="20" y1="{baseline:.1f}" x2="{width-20}" y2="{baseline:.1f}" stroke="#22314d" stroke-width="1"/>
      {''.join(rects)}
      <text x="28" y="18" fill="#25c27a" font-size="11">realized</text>
      <text x="96" y="18" fill="#ff6b6b" font-size="11">unrealized</text>
    </svg>
    '''
