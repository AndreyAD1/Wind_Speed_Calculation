import base64
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, abort
from flask_bootstrap import Bootstrap

from databases import check_db, WindIndicator, WeatherStation
from calculations import get_calculation_results
from constants import MONTH_LIST, MONTH_LIST_NUMBER
from exceptions import RP5FormatError

app = Flask(__name__)
Bootstrap(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/suggest', methods=['GET'])
def suggest():
    q = request.args.get('term').strip()
    if len(q) == 0:
        return abort(400)
    stations = WeatherStation.query\
        .filter(WeatherStation.id.like(q + '%'))\
        .order_by(WeatherStation.id)\
        .limit(500)
    station_list = []
    for station in stations:
        d = {
            'id': station.id,
            'name': station.name
        }
        station_list.append(d)
    return jsonify(station_list)


@app.route('/calculate', methods=['POST'])
def calculate():
    form = request.form
    station_id = form['station_id']
    start_date = form['from']
    end_date = form['to']
    storm_probability = form['storm_recurrence']
    selected_months = []
    for month_number in MONTH_LIST:
        # с помощью исключения составляю список выбранных месяцев
        try:
            month_status = form[month_number]
        except:
            continue
        selected_months.append(month_number)
    if not selected_months:
        selected_months = MONTH_LIST_NUMBER
    start_date = datetime.strptime(start_date, '%d.%m.%Y')
    # включаю в запрос последний день в интервале
    end_date = datetime.strptime(end_date, '%d.%m.%Y') + timedelta(days=1)
    # перехожу от обеспеченности в % к количеству лет
    storm_recurrence = 100/float(storm_probability)
    try:
        check_db(station_id, start_date, end_date)
    except RP5FormatError:
        return render_template('RP5error.html', station_id=station_id)
    data = []
    for month in selected_months:
        data.extend(WindIndicator.query.filter(WindIndicator.weather_station_id == station_id,
                                               WindIndicator.local_date <= end_date,
                                               WindIndicator.local_date >= start_date,
                                               WindIndicator.month == month).all())
    velocity, result_direction_speed, image_buf, legend_decoding_dict = get_calculation_results(
        data, storm_recurrence, selected_months
    )
    image_encoded = base64.b64encode(image_buf.getvalue()).decode('utf-8')

    station = WeatherStation.query.get(station_id)
    if station is not None:
        if len(station.name) > 0:
            station_id = station.name
    observation_dates = []
    for observation in data:
        observation_dates.append(observation.local_date)
    earliest_date = min(observation_dates)
    latest_date = max(observation_dates)

    return render_template(
        'calculate.html',
        station_id=station_id,
        start_date=earliest_date,
        end_date=latest_date,
        velocity_table=velocity,
        image=str(image_encoded),
        result_direction_speed=result_direction_speed,
        legend_decoding_dict=legend_decoding_dict,
        storm_probability=storm_probability,
        selected_months=selected_months
    )


if __name__ == '__main__':
    app.run(port=8080, debug=True)
