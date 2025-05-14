from flask import Blueprint, render_template
import pandas as pd
import plotly.express as px
import json


research_bp = Blueprint('research', __name__, url_prefix='/research')

@research_bp.route('/')
def research_view():
    """Display the research page (empty for now)."""
    return render_template('research.html', title='Research')

# @.route('/analysis')
# def analysis_view():
#     """Display the analysis page (empty for now)."""
#     return render_template('analysis.html', title='Analysis')

@research_bp.route("/analytics")
def analytics():
    df = pd.read_csv("C:\\Users\\ahanj\\OneDrive\\Documents\\Vetra\\data\\california_power_plants_with_weather.csv")

    summary = {
        "total_output": df["estimated_output"].sum(),
        "avg_efficiency": (df["estimated_output"] / df["Capacity_Latest"]).mean(),
        "top_county": df.groupby("County")["estimated_output"].sum().idxmax(),
        "co2_offset": df["estimated_output"].sum() * 0.9
    }

    # Build 4 Plotly charts
    fig1 = px.bar(df, x="PriEnergySource", y="estimated_output", title="Average Output by Source")
    fig2 = px.scatter(df, x="temperature", y="estimated_output", title="Temperature vs Solar Output")
    fig3 = px.scatter(df, x="wind_speed", y="estimated_output", title="Wind Speed vs Wind Output")
    fig4 = px.scatter(df, x="wind_speed", y="estimated_output", title="Wind Speed vs Wind Output")
    # fig4 = px.imshow(df.corr(), x="cloud_cover", y="estimated_output", title="Weather vs Output Correlation Matrix")

    graphJSON = {
        "avg_by_source": json.loads(fig1.to_json()),
        "temp_vs_solar": json.loads(fig2.to_json()),
        "wind_vs_output": json.loads(fig3.to_json()),
        "correlation": json.loads(fig4.to_json())
    }

    return render_template("analysis.html", summary=summary, graphJSON=graphJSON)