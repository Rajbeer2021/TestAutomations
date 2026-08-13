import os
import re
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

class DashboardGenerator:
    def __init__(self, base_dir="reports/custom_reports"):
        self.base_dir = base_dir
        self.dashboard_file = os.path.join(self.base_dir, "dashboard.html")
        self.history_file = os.path.join(self.base_dir, "dashboard_data.csv")

    # ----------------- Utility -----------------
    @staticmethod
    def format_seconds_to_hms(seconds: float) -> str:
        """Convert seconds to HH:MM:SS format"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ----------------- Find Report -----------------
    def _find_report_file(self, suite_dir):
        for file in os.listdir(suite_dir):
            if file.endswith("_report.html"):
                return os.path.join(suite_dir, file)
        return None

    # ----------------- Parse Report -----------------
    def _parse_report(self, report_path):
        data = {
            "name": os.path.basename(os.path.dirname(report_path)),
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "time": 0.0,
            "skipped_names": [],
            "report_link": os.path.relpath(report_path, self.base_dir).replace("\\", "/")
        }

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                html = f.read()

            total = re.search(r"Total\s*Tests[^0-9]*(\d+)", html)
            passed = re.search(r"Passed[^0-9]*(\d+)", html)
            failed = re.search(r"Failed[^0-9]*(\d+)", html)
            time_taken = re.search(r"(?:Total\s*Time|Duration)[^0-9]*(\d+)", html)

            if total: data["total"] = int(total.group(1))
            if passed: data["passed"] = int(passed.group(1))
            if failed: data["failed"] = int(failed.group(1))
            if time_taken: data["time"] = float(time_taken.group(1)) / 1000

            skipped_matches = []
            skipped_matches += re.findall(r'\[END TEST\].*—\s*SKIPPED', html, re.IGNORECASE)
            skipped_name_matches = re.findall(r'Skipped:\s*([^\n<]+)', html, re.IGNORECASE)
            skipped_matches += skipped_name_matches

            data["skipped"] = len(skipped_matches)
            data["skipped_names"] = [name.strip() for name in skipped_name_matches if name.strip()]

            if not data["total"]:
                data["total"] = data["passed"] + data["failed"] + data["skipped"]

        except Exception as e:
            print(f"[WARN] Failed to parse {report_path}: {e}")

        return data

    # ----------------- Collect Suite Data -----------------
    def collect_suite_data(self):
        suite_data = []
        if not os.path.exists(self.base_dir):
            print(f"[WARN] Base directory not found: {self.base_dir}")
            return suite_data

        for folder in sorted(os.listdir(self.base_dir)):
            suite_dir = os.path.join(self.base_dir, folder)
            if not os.path.isdir(suite_dir):
                continue
            report = self._find_report_file(suite_dir)
            if report:
                stats = self._parse_report(report)
                suite_data.append(stats)
        return suite_data

    # ----------------- Append History -----------------
    def _append_history(self, df):
        total_tests = df["total"].sum()
        passed = df["passed"].sum()
        failed = df["failed"].sum()
        skipped = df.get("skipped", pd.Series([0]*len(df))).sum()
        pass_rate = round((passed / total_tests) * 100 if total_tests else 0, 2)
        total_time = df["time"].sum()

        row = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": total_tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": pass_rate,
            "time": total_time,
        }

        if os.path.exists(self.history_file):
            old = pd.read_csv(self.history_file)
            old = pd.concat([old, pd.DataFrame([row])], ignore_index=True)
        else:
            old = pd.DataFrame([row])

        old.to_csv(self.history_file, index=False)
        return old

    # ----------------- Generate Dashboard -----------------
    def generate_dashboard(self):
        suite_data = self.collect_suite_data()
        if not suite_data:
            print("[DASHBOARD] No suite reports found.")
            return

        df = pd.DataFrame(suite_data)
        df["skipped"] = df.get("skipped", pd.Series([0]*len(df)))
        df["time_hms"] = df["time"].apply(lambda x: self.format_seconds_to_hms(x))
        total_time_sec = df["time"].sum()
        total_time_str = self.format_seconds_to_hms(total_time_sec)

        total_tests = df["total"].sum()
        total_passed = df["passed"].sum()
        total_failed = df["failed"].sum()
        total_skipped = df["skipped"].sum()

        history_df = self._append_history(df)

        # --- Donut Chart ---
        pass_percentage = round((total_passed / total_tests) * 100 if total_tests else 0, 1)
        pie_chart = go.Figure(data=[go.Pie(
            labels=["Passed", "Failed", "Skipped"],
            values=[total_passed, total_failed, total_skipped],
            hole=0.5,
            marker=dict(colors=["#22c55e", "#ef4444", "#facc15"]),
            hoverinfo="label+percent+value",
            textinfo='percent',
            textfont_size=20
        )])
        pie_chart.add_annotation(
            x=0.5, y=0.5,
            text=f"<b>{pass_percentage}%</b><br>Pass",
            showarrow=False,
            font=dict(size=22, color="#22c55e"),
            xanchor='center', yanchor='middle'
        )
        pie_chart.update_layout(
            title=dict(text="Overall Test Results", font=dict(size=18, color="#e2e8f0")),
            paper_bgcolor='#0f172a', plot_bgcolor='#0f172a', font_color='#e2e8f0',
            margin=dict(t=40, b=40, l=40, r=40)
        )

        # --- Bar Chart ---
        bar_chart = go.Figure()
        bar_chart.add_trace(go.Bar(
            y=df["name"], x=df["passed"], orientation='h',
            name="Passed", marker_color="#22c55e", hovertemplate='%{x} Passed'
        ))
        bar_chart.add_trace(go.Bar(
            y=df["name"], x=df["failed"], orientation='h',
            name="Failed", marker_color="#ef4444", hovertemplate='%{x} Failed'
        ))
        bar_chart.add_trace(go.Bar(
            y=df["name"], x=df["skipped"], orientation='h',
            name="Skipped", marker_color="#facc15", hovertemplate='%{x} Skipped'
        ))
        bar_chart.update_layout(title="Suite-wise Test Results",
                                barmode='stack', yaxis={'autorange':'reversed'},
                                plot_bgcolor='#0f172a', paper_bgcolor='#0f172a',
                                font_color='#e2e8f0')

        # --- Line Chart: Execution Time per Status ---
        df["time_passed"] = df["time"] * df["passed"] / df["total"]
        df["time_failed"] = df["time"] * df["failed"] / df["total"]
        df["time_skipped"] = df["time"] * df["skipped"] / df["total"]

        time_chart = go.Figure()
        time_chart.add_trace(go.Scatter(
            x=df["name"], y=df["time_passed"],
            mode='lines+markers',
            line=dict(color='#22c55e', width=3),
            name="Passed",
            hovertemplate=[self.format_seconds_to_hms(x) for x in df["time_passed"]]
        ))
        time_chart.add_trace(go.Scatter(
            x=df["name"], y=df["time_failed"],
            mode='lines+markers',
            line=dict(color='#ef4444', width=3),
            name="Failed",
            hovertemplate=[self.format_seconds_to_hms(x) for x in df["time_failed"]]
        ))
        time_chart.add_trace(go.Scatter(
            x=df["name"], y=df["time_skipped"],
            mode='lines+markers',
            line=dict(color='#facc15', width=3),
            name="Skipped",
            hovertemplate=[self.format_seconds_to_hms(x) for x in df["time_skipped"]]
        ))
        time_chart.update_layout(
            title="Execution Time per Suite (HH:MM:SS)",
            plot_bgcolor='#0f172a', paper_bgcolor='#0f172a',
            font_color='#e2e8f0', yaxis_title="Time (sec)"
        )

        # --- Line Chart: Pass Rate Trend ---
        trend_chart = go.Figure()
        trend_chart.add_trace(go.Scatter(
            x=history_df["timestamp"], y=history_df["pass_rate"],
            mode='lines+markers', line=dict(color='#10b981', width=3),
            name="Pass Rate (%)", hovertemplate='%{y} %'
        ))
        trend_chart.update_layout(title="Pass Rate Trend (Over Time)",
                                  plot_bgcolor='#0f172a', paper_bgcolor='#0f172a',
                                  font_color='#e2e8f0', xaxis_tickangle=-45)

        # --- Export charts ---
        pie_div = pie_chart.to_html(full_html=False, include_plotlyjs='cdn')
        bar_div = bar_chart.to_html(full_html=False, include_plotlyjs=False)
        time_div = time_chart.to_html(full_html=False, include_plotlyjs=False)
        trend_div = trend_chart.to_html(full_html=False, include_plotlyjs=False)

        # --- HTML Layout ---
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Automation Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body {{ background: linear-gradient(135deg, #0f172a 30%, #1e293b 70%, #334155); color:#e2e8f0; font-family:'Segoe UI', sans-serif; }}
.header {{ text-align:center; padding:25px; font-size:30px; font-weight:bold; color:#fff; text-shadow:0 0 15px rgba(255,255,255,0.3); }}
.card-custom {{ background: rgba(15,23,42,0.9); color:#fff; border-radius:15px; transition: transform 0.3s ease, box-shadow 0.3s ease; margin-bottom:20px; }}
.card-custom:hover {{ transform: scale(1.08); box-shadow: 0 0 25px rgba(255,255,255,0.3); }}
.table-custom th {{ background:#334155; color:#fff; }}
.table-custom tr:hover {{ background: rgba(51,65,85,0.8); transition:0.3s; }}
.badge-pass {{ background-color:#22c55e; transition:0.3s; }}
.badge-fail {{ background-color:#ef4444; transition:0.3s; }}
.badge-skip {{ background-color:#facc15; transition:0.3s; }}
.footer {{ text-align:center; color:#94a3b8; padding:15px; margin-top:25px; }}
</style>
</head>
<body>
<div class="header">Playwright Automation Dashboard</div>
<div class="container mt-4">

<div class="row text-center">
<div class="col-md card card-custom"><h5>Total Suites</h5><p>{len(df)}</p></div>
<div class="col-md card card-custom"><h5>Total Tests</h5><p>{total_tests}</p></div>
<div class="col-md card card-custom"><h5>Passed</h5><p class="text-success">{total_passed}</p></div>
<div class="col-md card card-custom"><h5>Failed</h5><p class="text-danger">{total_failed}</p></div>
<div class="col-md card card-custom"><h5>Skipped</h5><p class="text-warning">{total_skipped}</p></div>
<div class="col-md card card-custom"><h5>Total Time</h5><p class="text-info">{total_time_str}</p></div>
</div>

<div class="row mt-4 justify-content-center">
<div class="col-md-6">{pie_div}</div>
<div class="col-md-6">{bar_div}</div>
</div>

<div class="row mt-4">
<div class="col-md">{time_div}</div>
<div class="col-md">{trend_div}</div>
</div>

<h3 class="mt-5 text-info">Detailed Suite Summary</h3>
<table class="table table-striped table-custom">
<thead><tr>
<th>Suite Name</th><th>Total</th><th>Passed</th><th>Failed</th><th>Skipped</th><th>Time (HH:MM:SS)</th><th>Report</th>
</tr></thead>
<tbody>"""

        for _, s in df.iterrows():
            html += f"""
<tr>
<td>{s['name']}</td>
<td>{s['total']}</td>
<td><span class="badge badge-pass">{s['passed']}</span></td>
<td><span class="badge badge-fail">{s['failed']}</span></td>
<td><span class="badge badge-skip">{s['skipped']}</span></td>
<td>{s['time_hms']}</td>
<td><a href="{s['report_link']}" target="_blank" class="text-info">Open</a></td>
</tr>"""

        html += f"""
</tbody>
</table>
<div class="footer">
Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | © {datetime.now().year} Automation Framework
</div>
</div>
</body>
</html>"""

        os.makedirs(self.base_dir, exist_ok=True)
        with open(self.dashboard_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[DASHBOARD] ✅ Interactive dashboard updated: {self.dashboard_file}")
        return self.dashboard_file


if __name__ == "__main__":
    DashboardGenerator().generate_dashboard()
