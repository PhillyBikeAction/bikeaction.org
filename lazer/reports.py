import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils.html import escape


def script_json(value):
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def generate_html_report(
    violations,
    polygon,
    comparison_date,
    comparison_date_str,
    before_count,
    after_count,
    geojson_data,
    filter_mode,
    street_name=None,
    block_range=None,
    start_date=None,
    end_date=None,
    timezone_name="America/New_York",
):
    """Generate an HTML report with map, chart, and data table."""
    from collections import defaultdict

    street_name = escape(street_name or "")
    block_range = escape(block_range or "")

    # Prepare data for timeline chart
    from datetime import timedelta

    has_comparison = comparison_date is not None
    daily_counts = defaultdict(int)
    violation_list = []

    for report in violations:
        date_str = report.submission.captured_at.strftime("%Y-%m-%d")
        if has_comparison:
            period = "before" if report.submission.captured_at < comparison_date else "after"
        else:
            period = "all"
        daily_counts[date_str] += 1

        # Get violation details
        violation_type = report.violation_observed
        location = f"{report.block_number} {report.street_name}"

        violation_list.append(
            {
                "datetime": report.submission.captured_at.strftime("%Y-%m-%d %H:%M:%S"),
                "location": str(escape(location)),
                "type": str(escape(violation_type or "")),
                "lat": report.submission.location.y,
                "lon": report.submission.location.x,
                "period": period,
            }
        )

    # Create complete date range (all days including zeros)
    if violations:
        min_date = violations.earliest("submission__captured_at").submission.captured_at.date()
        max_date = violations.latest("submission__captured_at").submission.captured_at.date()

        chart_labels = []
        chart_data_before = []
        chart_data_after = []
        chart_data_all = []

        current_date = min_date
        days_before = 0
        days_after = 0
        total_days = 0

        if has_comparison:
            comparison_date_only = comparison_date.date()
            while current_date <= max_date:
                date_str = current_date.strftime("%Y-%m-%d")
                chart_labels.append(date_str)
                count = daily_counts.get(date_str, 0)

                if current_date < comparison_date_only:
                    chart_data_before.append(count)
                    chart_data_after.append(None)
                    days_before += 1
                else:
                    chart_data_before.append(None)
                    chart_data_after.append(count)
                    days_after += 1

                current_date += timedelta(days=1)
        else:
            while current_date <= max_date:
                date_str = current_date.strftime("%Y-%m-%d")
                chart_labels.append(date_str)
                count = daily_counts.get(date_str, 0)
                chart_data_all.append(count)
                total_days += 1
                current_date += timedelta(days=1)
    else:
        chart_labels = []
        chart_data_before = []
        chart_data_after = []
        chart_data_all = []
        days_before = 0
        days_after = 0
        total_days = 0

    # Calculate averages (only for comparison mode)
    if has_comparison:
        avg_before = before_count / days_before if days_before > 0 else 0
        avg_after = after_count / days_after if days_after > 0 else 0
        avg_change = avg_after - avg_before
        avg_percent_change = (avg_change / avg_before * 100) if avg_before > 0 else 0

    # Calculate map center
    if filter_mode == "geojson" and polygon:
        center_lat = polygon.centroid.y
        center_lon = polygon.centroid.x
    elif violations:
        # Calculate center from violations
        lats = [v.submission.location.y for v in violations]
        lons = [v.submission.location.x for v in violations]
        center_lat = sum(lats) / len(lats) if lats else 39.95
        center_lon = sum(lons) / len(lons) if lons else -75.16
    else:
        # Default to Philly center
        center_lat = 39.95
        center_lon = -75.16

    # Prepare polygon JavaScript code
    if filter_mode == "geojson":
        polygon_js = f"""const polygon = {script_json(geojson_data)};
    L.geoJSON(polygon, {{
        style: {{
            color: 'rgb(131, 189, 86)',
            weight: 3,
            fillOpacity: 0.1,
            fillColor: 'rgb(131, 189, 86)'
        }}
    }}).addTo(map);"""
    else:
        polygon_js = "// No polygon for street mode"

    # Prepare header subtitle
    if filter_mode == "street":
        header_subtitle = f"<p>{street_name}{(' Blocks ' + block_range) if block_range else ''}</p>"
        filter_info = f"<strong>Street:</strong> {street_name}"
        if block_range:
            filter_info += f"<br><strong>Block Range:</strong> {block_range}<br>"
        else:
            filter_info += "<br>"
    else:
        header_subtitle = ""
        filter_info = ""

    if start_date or end_date:
        filter_info += (
            f"<strong>Capture dates:</strong> {start_date or 'Beginning'}"
            f" through {end_date or 'Present'} ({escape(timezone_name)})<br>"
        )

    # Build info line
    if has_comparison:
        info_html = f"""{filter_info}
        <strong>Comparison Date:</strong> {comparison_date_str}"""
    else:
        info_html = filter_info

    # Build stats cards
    if has_comparison:
        stats_html = f"""
        <div class="stat-card">
            <h3>Total Violations</h3>
            <div class="value">{before_count + after_count}</div>
            <div class="subvalue">{days_before + days_after} days</div>
        </div>
        <div class="stat-card before">
            <h3>Avg Per Day Before</h3>
            <div class="value">{avg_before:.2f}</div>
            <div class="subvalue">{before_count} total / {days_before} days</div>
        </div>
        <div class="stat-card after">
            <h3>Avg Per Day After</h3>
            <div class="value">{avg_after:.2f}</div>
            <div class="subvalue">{after_count} total / {days_after} days</div>
        </div>
        <div class="stat-card change">
            <h3>Change in Avg</h3>
            <div class="value">{avg_change:+.2f}</div>
            <div class="subvalue">
                {avg_percent_change:+.1f}% per day
            </div>
        </div>"""
    else:
        stats_html = f"""
        <div class="stat-card">
            <h3>Total Violations</h3>
            <div class="value">{after_count}</div>
            <div class="subvalue">{total_days} days</div>
        </div>"""

    # Build table header and rows
    if has_comparison:
        table_header = """<tr>
                    <th>Date &amp; Time</th>
                    <th>Location</th>
                    <th>Violation Type</th>
                    <th>Period</th>
                </tr>"""
        table_rows = "".join(
            [
                f"""<tr>
                        <td>{v["datetime"]}</td>
                        <td>{v["location"]}</td>
                        <td>{v["type"]}</td>
                        <td class="period-{v["period"]}">{v["period"].upper()}</td>
                    </tr>"""
                for v in violation_list
            ]
        )
    else:
        table_header = """<tr>
                    <th>Date &amp; Time</th>
                    <th>Location</th>
                    <th>Violation Type</th>
                </tr>"""
        table_rows = "".join(
            [
                f"""<tr>
                        <td>{v["datetime"]}</td>
                        <td>{v["location"]}</td>
                        <td>{v["type"]}</td>
                    </tr>"""
                for v in violation_list
            ]
        )

    # Build marker JavaScript
    if has_comparison:
        marker_js = f"""const violations = {script_json(violation_list)};
    violations.forEach(v => {{
        const color = v.period === 'before' ? '#d8107d' : 'rgb(131, 189, 86)';
        const marker = L.circleMarker([v.lat, v.lon], {{
            radius: 6,
            fillColor: color,
            color: '#fff',
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8
        }}).addTo(map);

        marker.bindPopup(`
            <strong>${{v.datetime}}</strong><br>
            ${{v.location}}<br>
            ${{v.type}}<br>
            <em>${{v.period.toUpperCase()}}</em>
        `);
    }});"""
    else:
        marker_js = f"""const violations = {script_json(violation_list)};
    violations.forEach(v => {{
        const marker = L.circleMarker([v.lat, v.lon], {{
            radius: 6,
            fillColor: 'rgb(131, 189, 86)',
            color: '#fff',
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8
        }}).addTo(map);

        marker.bindPopup(`
            <strong>${{v.datetime}}</strong><br>
            ${{v.location}}<br>
            ${{v.type}}
        `);
    }});"""

    # Build chart JavaScript
    if has_comparison:
        chart_js = f"""const comparisonDate = '{comparison_date_str}';
    const labels = {json.dumps(chart_labels)};
    const dataBefore = {json.dumps(chart_data_before)};
    const dataAfter = {json.dumps(chart_data_after)};

    // Find index of comparison date
    const comparisonIndex = labels.indexOf(comparisonDate);

    new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [
                {{
                    label: 'Before {comparison_date_str}',
                    data: dataBefore,
                    borderColor: '#d8107d',
                    backgroundColor: 'rgba(216, 16, 125, 0.2)',
                    tension: 0.1,
                    fill: true,
                    pointBackgroundColor: '#d8107d',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    spanGaps: false
                }},
                {{
                    label: 'After {comparison_date_str}',
                    data: dataAfter,
                    borderColor: 'rgb(131, 189, 86)',
                    backgroundColor: 'rgba(131, 189, 86, 0.2)',
                    tension: 0.1,
                    fill: true,
                    pointBackgroundColor: 'rgb(131, 189, 86)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    spanGaps: false
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{
                    display: true
                }},
                annotation: {{
                    annotations: {{
                        line1: {{
                            type: 'line',
                            xMin: comparisonIndex,
                            xMax: comparisonIndex,
                            borderColor: '#dc3545',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            label: {{
                                content: 'Comparison Date',
                                enabled: true
                            }}
                        }}
                    }}
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    ticks: {{
                        stepSize: 1
                    }},
                    title: {{
                        display: true,
                        text: 'Violations per Day'
                    }}
                }},
                x: {{
                    ticks: {{
                        maxRotation: 45,
                        minRotation: 45,
                        autoSkip: true,
                        maxTicksLimit: 20
                    }},
                    title: {{
                        display: true,
                        text: 'Date'
                    }}
                }}
            }}
        }},
        plugins: [{{
            id: 'verticalLine',
            beforeDraw: (chart) => {{
                if (comparisonIndex >= 0 && comparisonIndex < labels.length) {{
                    const ctx = chart.ctx;
                    const xAxis = chart.scales.x;
                    const yAxis = chart.scales.y;
                    const x = xAxis.getPixelForValue(comparisonIndex);

                    ctx.save();
                    ctx.beginPath();
                    ctx.moveTo(x, yAxis.top);
                    ctx.lineTo(x, yAxis.bottom);
                    ctx.lineWidth = 3;
                    ctx.strokeStyle = '#d8107d';
                    ctx.setLineDash([5, 5]);
                    ctx.stroke();
                    ctx.restore();
                }}
            }}
        }}]
    }});"""
    else:
        chart_js = f"""const labels = {json.dumps(chart_labels)};
    const dataAll = {json.dumps(chart_data_all)};

    new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [
                {{
                    label: 'Violations',
                    data: dataAll,
                    borderColor: 'rgb(131, 189, 86)',
                    backgroundColor: 'rgba(131, 189, 86, 0.2)',
                    tension: 0.1,
                    fill: true,
                    pointBackgroundColor: 'rgb(131, 189, 86)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    spanGaps: false
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{
                    display: true
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    ticks: {{
                        stepSize: 1
                    }},
                    title: {{
                        display: true,
                        text: 'Violations per Day'
                    }}
                }},
                x: {{
                    ticks: {{
                        maxRotation: 45,
                        minRotation: 45,
                        autoSkip: true,
                        maxTicksLimit: 20
                    }},
                    title: {{
                        display: true,
                        text: 'Date'
                    }}
                }}
            }}
        }}
    }});"""

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Laser Vision Violation Report - Philly Bike Action</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@100..900&family=Ubuntu:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400;1,500;1,700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
    * {{
        box-sizing: border-box;
    }}
    body {{
        font-family: "Ubuntu", -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Cantarell, sans-serif;
        margin: 0;
        padding: 0;
        background: #f5f5f5;
        line-height: 1.6;
    }}
    .header {{
        background-color: rgb(131, 189, 86);
        padding: 1.5rem 2rem;
        color: white;
        text-align: center;
    }}
    .header h1 {{
        font-family: "Big Shoulders Display", sans-serif;
        font-weight: 900;
        text-transform: uppercase;
        font-size: 3em;
        margin: 0;
        line-height: 1;
    }}
    .header p {{
        font-size: 1.2em;
        margin: 0.5rem 0 0 0;
    }}
    .container {{
        max-width: 1400px;
        margin: 2rem auto;
        background: white;
        padding: 2rem;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}
    .stats {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }}
    .stat-card {{
        background: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 2px solid rgb(131, 189, 86);
        text-align: center;
    }}
    .stat-card.before {{
        border-color: #d8107d;
    }}
    .stat-card.after {{
        border-color: rgb(131, 189, 86);
    }}
    .stat-card.change {{
        border-color: #333;
    }}
    .stat-card h3 {{
        margin: 0 0 0.75rem 0;
        font-size: 0.9rem;
        color: #666;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}
    .stat-card .value {{
        font-family: "Big Shoulders Display", sans-serif;
        font-size: 3rem;
        font-weight: 700;
        color: #333;
        line-height: 1;
    }}
    .stat-card .subvalue {{
        font-size: 1rem;
        color: #666;
        margin-top: 0.5rem;
    }}
    #map {{
        height: 500px;
        margin: 1.5rem 0;
        border-radius: 0.5rem;
        border: 1px solid #ddd;
    }}
    #chart-container {{
        margin: 1.5rem 0;
        height: 400px;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 1.5rem 0;
        font-size: 1rem;
    }}
    th, td {{
        padding: 0.75rem;
        text-align: left;
    }}
    th {{
        background-color: rgb(131, 189, 86);
        color: white;
        font-weight: 600;
        border-bottom: 1px solid rgb(131, 189, 86);
    }}
    tr:first-of-type th:first-child {{
        border-top-left-radius: 0.5rem;
    }}
    tr:first-of-type th:last-child {{
        border-top-right-radius: 0.5rem;
    }}
    tbody tr {{
        border-bottom: 1px solid #dddddd;
    }}
    tbody tr:nth-of-type(even) {{
        background-color: #f3f3f3;
    }}
    tbody tr:last-of-type {{
        border-bottom: 2px solid rgb(131, 189, 86);
    }}
    tbody tr:hover {{
        background-color: #e8f5e9;
    }}
    .period-before {{
        color: #d8107d;
        font-weight: 600;
    }}
    .period-after {{
        color: rgb(131, 189, 86);
        font-weight: 600;
    }}
    .section {{
        margin: 3rem 0;
    }}
    .section h2 {{
        font-family: "Big Shoulders Display", sans-serif;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 2rem;
        color: #333;
        border-bottom: 3px solid rgb(131, 189, 86);
        padding-bottom: 0.5rem;
        margin-bottom: 1.5rem;
    }}
    .footer {{
        text-align: center;
        padding: 2rem;
        background-color: black;
        color: white;
        margin-top: 3rem;
    }}
    .footer a {{
        color: rgb(131, 189, 86);
        text-decoration: none;
    }}
    .footer a:hover {{
        text-decoration: underline;
    }}
    @media screen and (max-width: 768px) {{
        .header h1 {{
            font-size: 2rem;
        }}
        .container {{
            margin: 1rem;
            padding: 1rem;
        }}
        .stats {{
            grid-template-columns: 1fr;
        }}
        table {{
            font-size: 0.9rem;
        }}
        th, td {{
            padding: 0.5rem;
        }}
    }}

    /* Print styles for PDF generation */
    @media print {{
        body {{
            background: white;
        }}
        #map {{
            page-break-after: always;
        }}
        table {{
            page-break-inside: auto;
        }}
        thead {{
            display: table-header-group;
        }}
        tr {{
            page-break-inside: avoid;
            page-break-after: auto;
        }}
        /* Ensure colors print correctly */
        * {{
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
    }}
</style>
</head>
<body>
<div class="header">
    <h1>Laser Vision Violation Report</h1>
    {header_subtitle}
    <p>Philly Bike Action</p>
</div>

<div class="container">
    <p style="text-align: center; font-size: 1.1em; margin-bottom: 2rem;">
        {info_html}
    </p>

    <div class="stats">
        {stats_html}
    </div>

    <div class="section">
        <h2>Map View</h2>
        <div id="map"></div>
    </div>

    <div class="section">
        <h2>Violations Over Time</h2>
        <div id="chart-container">
            <canvas id="violationChart"></canvas>
        </div>
    </div>

    <div class="section">
        <h2>All Violations</h2>
        <table>
            <thead>
                {table_header}
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
</div>

<div class="footer">
    <p><strong>Philly Bike Action</strong></p>
    <p>Safe, usable, protected, interconnected bike infrastructure for Philadelphia.</p>
    <p><a href="https://bikeaction.org">bikeaction.org</a></p>
</div>

<script>
    // Initialize map with interaction disabled
    const map = L.map('map', {{
        scrollWheelZoom: false,
        dragging: false,
        zoomControl: false,
        doubleClickZoom: false,
        boxZoom: false,
        keyboard: false,
        touchZoom: false
    }}).setView([{center_lat}, {center_lon}], 16);

    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">' +
            'OpenStreetMap</a> contributors'
    }}).addTo(map);

    {polygon_js}

    // Add violation markers
    {marker_js}

    // Initialize chart
    const ctx = document.getElementById('violationChart').getContext('2d');
    {chart_js}
</script>
</body>
</html>
"""
    return html


def filter_violation_reports(
    queryset,
    *,
    polygon=None,
    street_name=None,
    block_range=None,
    start_date=None,
    end_date=None,
    timezone_name="America/New_York",
):
    """Apply the command's area filters to an already permission-scoped queryset."""
    tz = ZoneInfo(timezone_name)
    if start_date:
        queryset = queryset.filter(
            submission__captured_at__gte=datetime.combine(start_date, time.min, tzinfo=tz)
        )
    if end_date:
        queryset = queryset.filter(
            submission__captured_at__lt=datetime.combine(
                end_date + timedelta(days=1), time.min, tzinfo=tz
            )
        )
    if polygon is not None:
        violations_in_area = (
            queryset.filter(submission__location__within=polygon)
            .select_related("submission")
            .order_by("submission__captured_at")
        )
    else:  # street mode
        # Start with street name filter
        violations_in_area = (
            queryset.filter(street_name__icontains=street_name)
            .select_related("submission")
            .order_by("submission__captured_at")
        )

        # If block range is provided, filter by it
        if block_range:
            if "-" in block_range:
                # Range format: "100-300"
                min_block, max_block = block_range.split("-")
                min_block = int(min_block.strip())
                max_block = int(max_block.strip())

                # Filter by extracting numeric part of block_number
                filtered_violations = []
                for v in violations_in_area:
                    try:
                        # Extract first number from block_number
                        block_num = int("".join(filter(str.isdigit, v.block_number.split()[0])))
                        if min_block <= block_num <= max_block:
                            filtered_violations.append(v.id)
                    except (ValueError, AttributeError, IndexError):
                        pass

                violations_in_area = violations_in_area.filter(id__in=filtered_violations)
            else:
                # Single block number
                target_block = block_range.strip()
                violations_in_area = violations_in_area.filter(block_number__icontains=target_block)

    return violations_in_area
