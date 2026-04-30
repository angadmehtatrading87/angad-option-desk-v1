def card(title, body, subtitle=""):
    sub = f'<div class="card-subtitle">{subtitle}</div>' if subtitle else ""
    return f"""
    <section class="card">
      <div class="card-header">
        <div>
          <div class="card-title">{title}</div>
          {sub}
        </div>
      </div>
      <div class="card-body">{body}</div>
    </section>
    """

def metric(label, value, tone="neutral"):
    return f"""
    <div class="metric metric-{tone}">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
    </div>
    """

def pill(text, cls="neutral"):
    return f'<span class="pill pill-{cls}">{text}</span>'

def table(headers, rows):
    th = "".join([f"<th>{h}</th>" for h in headers])
    trs = []
    for row in rows:
        trs.append("<tr>" + "".join([f"<td>{c}</td>" for c in row]) + "</tr>")
    if not trs:
        trs.append(f'<tr><td colspan="{len(headers)}">No data.</td></tr>')
    return f"""
    <div class="table-wrap">
      <table class="desk-table">
        <thead><tr>{th}</tr></thead>
        <tbody>{''.join(trs)}</tbody>
      </table>
    </div>
    """
