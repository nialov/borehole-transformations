import bisect
import pandas as pd
from pathlib import Path
import configparser
import json

from drillcore_transformations_py.drillcore_transformations import transform_with_gamma, transform_without_gamma

# Identifiers within the module. DO NOT CHANGE TO MATCH YOUR DATA FILE COLUMNS.
# Matching your data file to module identifiers is done in the config file (column_names.ini).
_ALPHA, _BETA, _GAMMA, _MEASUREMENT_DEPTH, _DEPTH, _BOREHOLE_TREND, _BOREHOLE_PLUNGE = \
	"alpha", "beta", "gamma", "measurement_depth", "depth", "borehole_trend", "borehole_plunge"

# Headers within config.
_MEASUREMENTS, _DEPTHS, _BOREHOLE = "MEASUREMENTS", "DEPTHS", "BOREHOLE"

# Config filename
_CONFIG = "column_names.ini"

class ColumnException(Exception):
	"""
	ColumnException is raised when there are errors with the columns of your data. These can be related to not
	recognizing the column or if multiple columns match identifiers in column_names.ini.

	Most issues can be fixed by checking the column_names.ini config file and adding your data file column names
	as identifiers or by removing identical identifiers.
	"""

def check_config(method):
	def inner(*args, **kwargs):
		assert Path(_CONFIG).exists()
		result = method(*args, **kwargs)
		return result
	return inner

def initialize_config():
	"""
	Creates a configfile with default names for alpha, beta, etc. Filename will be column_names.ini. Manual editing
	of this file is allowed but editing methods are also present for adding column names.
	"""
	config = configparser.ConfigParser()

	# Measurement file identifiers
	config[_MEASUREMENTS] = {}
	config[_MEASUREMENTS][_ALPHA] = json.dumps([_ALPHA, "ALPHA", "ALPHA_CORE"])
	config[_MEASUREMENTS][_BETA] = json.dumps([_BETA, "BETA", "BETA_CORE"])
	config[_MEASUREMENTS][_GAMMA] = json.dumps([_GAMMA, "GAMMA", "GAMMA_CORE"])
	config[_MEASUREMENTS][_MEASUREMENT_DEPTH] = json.dumps([_MEASUREMENT_DEPTH, "MEASUREMENT_DEPTH", "LENGTH_FROM"])

	# Depth file identifiers
	config[_DEPTHS] = {}
	config[_DEPTHS][_DEPTH] = json.dumps([_DEPTH, "DEPTH"])

	# Borehole trend and plunge identifiers
	config[_BOREHOLE] = {}
	config[_BOREHOLE][_BOREHOLE_TREND] = json.dumps([_BOREHOLE_TREND, "BOREHOLE_TREND", "AZIMUTH"])
	config[_BOREHOLE][_BOREHOLE_PLUNGE] = json.dumps([_BOREHOLE_PLUNGE, "BOREHOLE_PLUNGE", "INCLINATION", "inclination"])

	# Write to .ini file. Will overwrite old one or make a new one.
	with open(_CONFIG, "w+") as configfile:
		config.write(configfile)


def add_column_name(header, base_column, name):
	"""
	Method for adding a column name to recognize measurement type. E.g. if your alpha measurements are in a column
	that is named "alpha_measurements" you can add it to the column_names.ini file with:

	>>>add_column_name(_MEASUREMENTS, _ALPHA, "alpha_measurements")

	:param header: You may add new column names to the measurements file and to the file containing measurement depth
		information.
	:type header: str
	:param base_column: Which type of measurement is the column name.
		Base types for measurements are:
		"alpha" "beta" "gamma" "measurement_depth"
		Base types for depths are:
		"depth"
		Base types for borehole are:
		"borehole_trend" "borehole_plunge"
	:type base_column: str
	:param name: Name of the new column you want to add.
	:type name: str
	"""
	assert header in [_MEASUREMENTS, _DEPTHS, _BOREHOLE]
	config = configparser.ConfigParser()
	configname = _CONFIG
	if not Path(configname).exists():
		print("column_names.ini configfile not found. Making a new one with default values.")
		initialize_config()
	assert Path(configname).exists()
	config.read(configname)
	column_list = json.loads(config.get(header, base_column))

	assert isinstance(column_list, list)
	column_list.append(name)
	config[header][base_column] = json.dumps(column_list)
	save_config(config)


def save_config(config):
	# Write to .ini file. Will overwrite or make a new one.
	with open(_CONFIG, "w+") as configfile:
		config.write(configfile)


@check_config
def parse_column(header, base_column, columns):
	"""
	Finds a given base_column in given columns by trying to match it to identifiers in column_names.ini

	Example:

	>>> parse_column("BOREHOLE", _BOREHOLE_TREND, ["borehole_trend", "alpha", "beta", "borehole_plunge"])
	'borehole_trend'

	:param header: "MEASUREMENTS", "DEPTHS" or "BOREHOLE"
	:type header: str
	:param base_column: The base measurement type to identify. (E.g. "alpha", "beta")
	:type base_column: str
	:param columns: Columns from given data file.
	:type columns: list
	:return: Column name in your data file that matches the given base_column
	:rtype: str
	:raises ColumnException: When there are problems with identifying columns.
	"""
	config = configparser.ConfigParser()
	assert Path(_CONFIG).exists()
	config.read(_CONFIG)
	column_identifiers = json.loads(config.get(header, base_column))
	assert isinstance(column_identifiers, list)
	matching_columns = list(set(column_identifiers) & set(columns))

	# Check for errors
	if len(matching_columns) == 0:
		raise ColumnException(f"{base_column} of {header} was not recognized in columns of given file. \n"
							  f"Columns:{columns}\n"
							  f"Column identifiers in column_names.ini: {column_identifiers}\n"
						f"You must add it to column_names.ini as an identifier for recognition. \n"
						f"{Path('column_names.ini').absolute()}\n")
	if len(matching_columns) > 1:
		raise ColumnException(f"Multiple {base_column} type column names were found in identifiers. \n"
						f"Check column_names.ini file for identical identifiers. \n"
						f"{Path('column_names.ini').absolute()}\n"
						f"(E.g. alpha_measurement is in both ALPHA and BETA)\n")

	# Column in column_names.ini & given columns that matches given base_column
	return matching_columns[0]


@check_config
def parse_columns_two_files(columns, with_gamma):
	"""
	Matches columns to column bases in column_names.ini. Used when there's a separate file with depth data.

	Example:

	>>>parse_columns_two_files(["alpha", "beta", "gamma", "borehole_trend", "borehole_plunge", "depth", \
	"measurement_depth"], True)
	{'depth': 'depth', 'borehole_trend': 'borehole_trend', 'borehole_plunge':
	'borehole_plunge', 'alpha': 'alpha', 'beta': 'beta', 'gamma': 'gamma', 'measurement_depth': 'measurement_depth'}

	:param columns: Given columns
	:type columns: list
	:param with_gamma: Whether there are gamma measurements in file or not.
	:type with_gamma: bool
	:return: Matched columns as a dictionary.
	:rtype: dict
	"""
	# depths file
	find_columns_d = [_DEPTH]
	find_columns_bh = [_BOREHOLE_TREND, _BOREHOLE_PLUNGE]
	# measurements file
	if with_gamma:
		find_columns_m = [_ALPHA, _BETA, _GAMMA, _MEASUREMENT_DEPTH]
	else:
		find_columns_m = [_ALPHA, _BETA, _MEASUREMENT_DEPTH]

	matched_dict = dict()
	for f in find_columns_d:
		col = parse_column(_DEPTHS, f, columns)
		matched_dict[f] = col
	for f in find_columns_bh:
		col = parse_column(_BOREHOLE, f, columns)
		matched_dict[f] = col
	for f in find_columns_m:
		col = parse_column(_MEASUREMENTS, f, columns)
		matched_dict[f] = col
	if with_gamma:
		assert len(matched_dict) == 7
	else:
		assert len(matched_dict) == 6
	return matched_dict


@check_config
def parse_columns_one_file(columns, with_gamma):
	"""
	Matches columns to column bases in column_names.ini. Used when there is only one data file with all required
	data. I.e. at minimum: alpha, beta, borehole trend, borehole plunge

	If gamma data exists => with_gamma should be given as True

	Example:

	>>> parse_columns_one_file(["alpha", "beta", "borehole_trend", "borehole_plunge"], False)
	{'BOREHOLE_TREND': 'borehole_trend', 'BOREHOLE_PLUNGE': 'borehole_plunge', 'ALPHA': 'alpha', 'BETA': 'beta'}

	:param columns: Given columns
	:type columns: list
	:param with_gamma: Whether there are gamma measurements in file or not.
	:type with_gamma: bool
	:return: Matched columns as a dictionary.
	:rtype: dict
	"""
	find_columns_bh = [_BOREHOLE_TREND, _BOREHOLE_PLUNGE]
	# measurements file
	if with_gamma:
		find_columns_m = [_ALPHA, _BETA, _GAMMA]
	else:
		find_columns_m = [_ALPHA, _BETA]

	matched_dict = dict()
	for f in find_columns_bh:
		col = parse_column(_BOREHOLE, f, columns)
		matched_dict[f] = col
	for f in find_columns_m:
		col = parse_column(_MEASUREMENTS, f, columns)
		matched_dict[f] = col

	# Check that all are found. Exceptions should be raised in parse_column if not successfully found i.e. this in
	# only a backup/debug.
	if with_gamma:
		assert len(matched_dict) == 5
	else:
		assert len(matched_dict) == 4

	return matched_dict

def round_outputs(number):
	return round(number, 2)

def transform_csv(filename, output=None, with_gamma=False):
	"""
	Transforms data from a given .csv file. File must have columns with alpha and beta measurements and borehole trend
	and plunge.

	Saves new .csv file in the same directory.

	:param filename: Path to file for reading.
	:type filename: str
	:param output: Path for output file. Will default filename+_transformed.csv.
	:type output: str
	:param with_gamma: Do gamma calculations or not
	:type with_gamma: bool
	"""
	df = pd.read_csv(filename, sep=';')
	col_dict = parse_columns_one_file(df.columns.tolist(), with_gamma)
	# Creates and calculates new columns
	if with_gamma:
		df[['plane_dip', 'plane_dir', 'gamma_plunge', 'gamma_trend']] = df.apply(
			lambda row: pd.Series(transform_with_gamma(
				row[col_dict[_ALPHA]], row[col_dict[_BETA]], row[col_dict[_BOREHOLE_TREND]], row[col_dict[_BOREHOLE_PLUNGE]], row[col_dict[_GAMMA]])), axis=1)
		df[['plane_dip', 'plane_dir', 'gamma_plunge', 'gamma_trend']] = df[['plane_dip', 'plane_dir', 'gamma_plunge', 'gamma_trend']].applymap(round_outputs)
	else:
		df[['plane_dip', 'plane_dir']] = df.apply(
			lambda row: pd.Series(transform_without_gamma(
				row[col_dict[_ALPHA]], row[col_dict[_BETA]], row[col_dict[_BOREHOLE_TREND]], row[col_dict[_BOREHOLE_PLUNGE]])), axis=1)
		df[['plane_dip', 'plane_dir']] = df[['plane_dip', 'plane_dir']].applymap(round_outputs)

	# Savename
	if output is not None:
		savepath = Path(output)
	else:
		savename = Path(filename).stem.split('.')[0] + '_transformed.csv'
		savedir = str(Path(filename).parent)
		savepath = Path(savedir + "/" + savename)
	# Save new .csv. Overwrites old and creates new if needed.
	df.to_csv(savepath, sep=';', mode='w+')

def transform_excel(measurement_filename, with_gamma, output=None):
	measurements = pd.read_excel(measurement_filename)
	col_dict = parse_columns_two_files(measurements.columns.tolist(), with_gamma)

	# ALPHA must be reversed to achieve correct result.
	measurements[['plane_dip', 'plane_dir']] = measurements.apply(
		lambda row: pd.Series(transform_without_gamma(
			-row[col_dict[_ALPHA]], row[col_dict[_BETA]], row[col_dict[_BOREHOLE_TREND]], row[col_dict[_BOREHOLE_PLUNGE]])), axis=1)
	measurements[['plane_dip', 'plane_dir']] = \
		measurements[['plane_dip', 'plane_dir']].applymap(round_outputs)

	# Savename
	if output is not None:
		savepath = Path(output)
	else:
		savename = Path(measurement_filename).stem.split('.')[0] + '_transformed.csv'
		savedir = str(Path(measurement_filename).parent)
		savepath = Path(savedir + "/" + savename)
	# Save new .csv. Overwrites old and creates new if needed.
	measurements.to_csv(savepath, sep=';', mode='w+')

def transform_csv_two_files(measurement_filename, depth_filename, with_gamma, output=None):
	measurements = pd.read_csv(measurement_filename, sep=';')
	depth = pd.read_csv(depth_filename, sep=';')
	col_dict = parse_columns_two_files(measurements.columns.tolist() + depth.columns.tolist(), with_gamma)
	trend_plunge = []
	for idx, row in measurements.iterrows():
		val = row[col_dict[_MEASUREMENT_DEPTH]]
		right = bisect.bisect(depth[col_dict[_DEPTH]].values, val)
		if right == len(depth):
			right = right - 1
		# Check if index is -1 in which case right and left both work. Depth must be ordered!
		left = right - 1 if right - 1 != -1 else right

		# Check which is closer, left or right to value.
		take = right if depth[col_dict[_DEPTH]].iloc[right] - val <= val - depth[col_dict[_DEPTH]].iloc[left] else left
		trend, plunge = depth[[col_dict[_BOREHOLE_TREND], col_dict[_BOREHOLE_PLUNGE]]].iloc[take]
		plunge = -plunge
		trend_plunge.append((trend, plunge))

	measurements["borehole_trend"], measurements["borehole_plunge"] = \
		[tr[0] for tr in trend_plunge], [tr[1] for tr in trend_plunge]
	# dict must be updated with new fields in measurements file.
	col_dict[_BOREHOLE_TREND], col_dict[_BOREHOLE_PLUNGE] = "borehole_trend", "borehole_plunge"

	# ALPHA must be reversed to achieve correct result.
	measurements[['plane_dip', 'plane_dir']] = measurements.apply(
		lambda row: pd.Series(transform_without_gamma(
			-row[col_dict[_ALPHA]], row[col_dict[_BETA]], row[col_dict[_BOREHOLE_TREND]], row[col_dict[_BOREHOLE_PLUNGE]])), axis=1)
	measurements[['plane_dip', 'plane_dir']] = \
		measurements[['plane_dip', 'plane_dir']].applymap(round_outputs)

	# Savename
	if output is not None:
		savepath = Path(output)
	else:
		savename = Path(measurement_filename).stem.split('.')[0] + '_transformed.csv'
		savedir = str(Path(measurement_filename).parent)
		savepath = Path(savedir + "/" + savename)
	# Save new .csv. Overwrites old and creates new if needed.
	measurements.to_csv(savepath, sep=';', mode='w+')


def transform_excel_two_files(measurement_filename, depth_filename, with_gamma, output=None):
	measurements = pd.read_excel(measurement_filename)
	depth = pd.read_excel(depth_filename)
	col_dict = parse_columns_two_files(measurements.columns.tolist() + depth.columns.tolist(), with_gamma)
	trend_plunge = []
	for idx, row in measurements.iterrows():
		val = row[col_dict[_MEASUREMENT_DEPTH]]
		right = bisect.bisect(depth[col_dict[_DEPTH]].values, val)
		if right == len(depth):
			right = right - 1
		# Check if index is -1 in which case right and left both work. Depth must be ordered!
		left = right - 1 if right - 1 != -1 else right

		# Check which is closer, left or right to value.
		take = right if depth[col_dict[_DEPTH]].iloc[right] - val <= val - depth[col_dict[_DEPTH]].iloc[left] else left
		trend, plunge = depth[[col_dict[_BOREHOLE_TREND], col_dict[_BOREHOLE_PLUNGE]]].iloc[take]
		plunge = -plunge
		trend_plunge.append((trend, plunge))

	measurements["borehole_trend"], measurements["borehole_plunge"] = \
		[tr[0] for tr in trend_plunge], [tr[1] for tr in trend_plunge]
	# dict must be updated with new fields in measurements file.
	col_dict[_BOREHOLE_TREND], col_dict[_BOREHOLE_PLUNGE] = "borehole_trend", "borehole_plunge"

	# ALPHA must be reversed to achieve correct result.
	measurements[['plane_dip', 'plane_dir']] = measurements.apply(
		lambda row: pd.Series(transform_without_gamma(
			-row[col_dict[_ALPHA]], row[col_dict[_BETA]], row[col_dict[_BOREHOLE_TREND]], row[col_dict[_BOREHOLE_PLUNGE]])), axis=1)
	measurements[['plane_dip', 'plane_dir']] = \
		measurements[['plane_dip', 'plane_dir']].applymap(round_outputs)

	# Savename
	if output is not None:
		savepath = Path(output)
	else:
		savename = Path(measurement_filename).stem.split('.')[0] + '_transformed.csv'
		savedir = str(Path(measurement_filename).parent)
		savepath = Path(savedir + "/" + savename)
	# Save new .csv. Overwrites old and creates new if needed.
	measurements.to_csv(savepath, sep=';', mode='w+')

def main():
	initialize_config()
	add_column_name(_BOREHOLE, _BOREHOLE_PLUNGE, "DIP")
	transform_excel_two_files(r"F:\Users\nikke\Desktop\olkiluoto_data\KR55_raot.xlsx"
							   , r"F:\Users\nikke\Desktop\olkiluoto_data\KR55_taipuma.xlsx", False)


if __name__ == "__main__":
	main()
