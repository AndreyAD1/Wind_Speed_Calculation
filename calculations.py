# Андрей Аракельянц. 23.01.2018
# Задача этой программы - по данным наблюдений с сайта rp5.ru рассчитать
# скорость ветра заданной обеспеченности по каждому румбу.

from pandas import *
import io

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy
from constants import (
    WIND_SPEED, WIND_DIRECTION, CALM, ALL,
    STORM_DURATION, COEF, MINIMAL_TICK,
    MAXIMAL_TICK, TICKS_NUMBER, MINIMAL_X, MINIMAL_Y, MAXIMAL_Y, PER_CENT
)
from datetime import datetime


def get_pivot_table(data):
    direction = []
    speed = []
    for observation in data:
        direction.append(observation.wind_direction)
        speed.append(observation.wind_speed)
    observation_data = {WIND_SPEED: speed, WIND_DIRECTION: direction}
    required_data = pandas.DataFrame(data=observation_data)
    # добавляю вспомогательный столбец, который нужен для создания сводной
    # таблицы
    required_data = required_data.assign(Wind_speed_dublicate=required_data[WIND_SPEED])
    # создаю сводную таблицу с количеством наблюдений по каждому сочетанию
    # скорости-направления ветра. Строки таблицы - скорость ветра. Столбцы таблицы - направление ветра.
    velocity_direction_table = pandas.pivot_table(
        required_data, index=WIND_SPEED, values='Wind_speed_dublicate', columns=WIND_DIRECTION,
        margins=True, aggfunc=numpy.size
    )
    velocity_direction_table = velocity_direction_table.fillna(value=0)
    return velocity_direction_table


# Обрабатываю случаи штилей
# Нужно распределить штили равномерно по всем направлениями ветра.
# количество колонок в таблице
def process_calm_cases(velocity_direction_table):
    column_number = len(velocity_direction_table.columns)
    calm_cases = velocity_direction_table.loc[0, CALM]
    #  Вычитаю 2 из общего числа колонок, так как две правые колонки - это "All" и "Штиль, безветрие"
    calm_cases_per_each_direction = calm_cases / (column_number - 2)
    return calm_cases_per_each_direction


def get_table_2(velocity_direction_table, direction_list):
    # делаю таблицу с повторяемостью градаций в каждом румбе в процентах (таблица 3.2)
    for direction in direction_list:
        cases_with_this_direction = velocity_direction_table.loc[ALL, direction]
        velocity_direction_table[direction] = velocity_direction_table[direction] / cases_with_this_direction
    # удаляю столбец "All", потому что он не нужен
    velocity_direction_table = velocity_direction_table.drop(columns=ALL)
    velocity_direction_table = velocity_direction_table * PER_CENT
    return velocity_direction_table


# делаю таблицу с продолжительностью каждой градации по каждому
# направлению (таблица 3.3)
def get_table_3(velocity_direction_table):
    # добавить исключение
    # рассчитываю количество строк в таблице
    row_number = len(velocity_direction_table.iloc[:, 1])
    # обнуляю самую нижнюю строку таблицы
    # TODO fix scenario with row_number = 0
    velocity_direction_table.iloc[row_number - 1] = 0
    # TODO fix scenario with row_number = 0
    row_index = row_number - 2
    # делаю таблицу с продолжительностью каждой градации по каждому
    # направлению (таблица 3.3)
    while row_index != -1:
        velocity_direction_table.iloc[row_index] += velocity_direction_table.iloc[row_index + 1]
        row_index -= 1
    # заменяю название строки All на значение скорости ветра, который не
    # наблюдался
    max_observed_wind_velocity = velocity_direction_table.index[row_number - 2]
    # TODO variable with _2 in name is BAD, maybe you can just
    # TODO velocity_direction_table.rename({'All': (max_observed_wind_velocity + 1)}, axis='index')
    velocity_direction_table_2 = velocity_direction_table.rename(
        {ALL: (max_observed_wind_velocity + 1)}, axis='index')
    return velocity_direction_table_2


# вычисляю скорость ветра по значению режимной функции
def get_wind_speed(f_big, velocity_direction_table, column_name):
    row_number = 0

    for duration in velocity_direction_table.loc[:, column_name]:
        if f_big < duration:
            row_number += 1
            continue

        if f_big == duration:
            return velocity_direction_table.index[row_number]

        lower_wind_speed = velocity_direction_table.index[row_number - 1]
        bigger_wind_speed = velocity_direction_table.index[row_number]
        bigger_duration = velocity_direction_table.loc[
            lower_wind_speed, column_name]
        durations = numpy.array([duration, bigger_duration])
        speeds = numpy.array([bigger_wind_speed, lower_wind_speed])
        # вычисляю нужную нам скорость ветра, линейно интерполируя между
        # строками таблицы 3.3
        return numpy.interp(f_big, durations, speeds)


# вычисляем значение режимной функции F по формуле (3.1) и рассчитываю
# скорость ветра
def calculate_speed(direction_recurrence_table, velocity_direction_table, storm_recurrence,
                    start_date, end_date, direction_list):
    start_date = datetime.strptime(start_date, '%d.%m.%Y')
    end_date = datetime.strptime(end_date, '%d.%m.%Y')
    # выбрал 2016 год, потому что он високосный и ему подойдёт любая дата
    start_date_without_year = start_date.replace(year=2016)
    end_date_without_year = end_date.replace(year=2016)
    time_difference = end_date_without_year - start_date_without_year
    days_number = 365
    if time_difference.days > 0:
        days_number = time_difference.days

    column_number = 0
    wind_speed_dict = {}
    for direction_recurrence in direction_recurrence_table.loc['All']:
        f_big = COEF * STORM_DURATION / (days_number * storm_recurrence * direction_recurrence)
        # вычисляю скорость ветра по значению режимной функции, линейно
        # интерполируя между строками таблицы 3.3
        wind_speed = get_wind_speed(f_big, velocity_direction_table, direction_list[column_number])
        wind_speed = round(wind_speed, 1)
        wind_speed_dict.update({direction_list[column_number]: wind_speed})
        column_number += 1
    return wind_speed_dict


def get_picture(velocity_direction_table, direction_list):
    # TODO сделать так, чтобы расшифровка легенды совпадала с выводом расчётных скоростей
    velocity_axis = velocity_direction_table.index.values
    figure = plt.figure()
    left_graphs = figure.add_subplot(1, 2, 1)
    right_graphs = figure.add_subplot(1, 2, 2)
    graph_number = 0
    legend_decoding = {}
    for direction in direction_list:
        graph_number += 1
        duration_axis = velocity_direction_table[direction].values
        legend_decoding.update({graph_number: direction})
        # рисую график на левых осях. Если графиков на левых осях становится
        # больше 8, то рисую графики на правых осях
        if graph_number <= 8:
            left_graphs.plot(velocity_axis, duration_axis, label=graph_number)
        else:
            right_graphs.plot(velocity_axis, duration_axis, label=graph_number)
    y_labels = numpy.geomspace(MINIMAL_TICK, MAXIMAL_TICK, TICKS_NUMBER)
    maximal_x = velocity_axis.max()
    for picture in [left_graphs, right_graphs]:
        # делаю вертикальную ось логарифмической c симметрией относительно 0,
        # при значениях ниже 1 рисуется прямая линия
        picture.set_yscale('symlog', linthreshy=1)
        picture.set_yticks(y_labels)
        picture.yaxis.set_major_formatter(ticker.ScalarFormatter())
        picture.axis([MINIMAL_X, maximal_x, MAXIMAL_Y, MINIMAL_Y])
        picture.legend()
        picture.set_ylabel('F, %', rotation='horizontal', position=(0, 0.96))
        picture.set_xlabel('v, м/с', position=(1, 0))

    # немного увеличиваю расстояние между левым и правым рисунком
    plt.tight_layout(w_pad=1)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=400)
    # plt.savefig('picture.png', format='png', dpi=400)
    buf.seek(0)
    return buf


def get_calculation_results(data, storm_recurrence, start_date, end_date):
    velocity_direction_table = get_pivot_table(data)
    observations_number = velocity_direction_table.loc[ALL, ALL]
    direction_list = []
    for direction in velocity_direction_table.columns:
        direction_list.append(direction)
    if direction_list.count(CALM) > 0:
        calm_cases_per_each_direction = process_calm_cases(velocity_direction_table)
        velocity_direction_table.loc[0] = calm_cases_per_each_direction
        velocity_direction_table.loc[ALL] = velocity_direction_table.loc[ALL] + calm_cases_per_each_direction
        velocity_direction_table = velocity_direction_table.drop(columns=CALM)

    # делаю таблицу с повторяемостью градаций от общего числа всех наблюдений
    # (таблица 3.1)
    direction_recurrence_table = velocity_direction_table / observations_number
    direction_recurrence_table = direction_recurrence_table.drop(columns=ALL)
    direction_list = []
    for direction in direction_recurrence_table.columns:
        direction_list.append(direction)
    # делаю таблицу с повторяемостью градаций в каждом румбе в процентах (таблица 3.2)
    velocity_direction_table = get_table_2(velocity_direction_table, direction_list)
    # делаю таблицу с продолжительностью каждой градации по каждому
    # направлению (таблица 3.3)
    velocity_direction_table = get_table_3(velocity_direction_table)
    # делаю рисунок режимных функций ветра по каждому направлению (рисунок 1)
    image_buf = get_picture(velocity_direction_table, direction_list)
    # рассчитываю значение режимной функции для каждого направления ветра
    calculated_wind_speed = calculate_speed(direction_recurrence_table, velocity_direction_table,
                                            storm_recurrence, start_date, end_date, direction_list
                                            )
    return velocity_direction_table, calculated_wind_speed, image_buf


if __name__ == '__main__':
    get_calculation_results()
