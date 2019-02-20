#!/usr/bin/env python3

import sys
import argparse
import os
import types
import se
import se.formatting
import se.typography
from se.se_epub import SeEpub


def main() -> int:
	# Generate a list of available commands from all of the functions in this file.
	commands = []
	for item, value in globals().items():
		if isinstance(value, types.FunctionType) and item != "main":
			commands.append(item.replace("_", "-"))

	commands.sort()

	parser = argparse.ArgumentParser(description="The entry point for the Standard Ebooks toolset.")
	parser.add_argument("command", metavar="COMMAND", choices=commands, help="one of: " + " ".join(commands))
	parser.add_argument("arguments", metavar="ARGS", nargs="*", help="arguments for the subcommand")
	args = parser.parse_args(sys.argv[1:2])

	# Remove the command name from the list of passed args.
	sys.argv.pop(1)

	# Change the command name so that argparse instances in child functions report the correct command on help/error.
	sys.argv[0] = args.command

	# Now execute the command
	return globals()[args.command.replace("-", "_")]()

def british2american() -> int:
	parser = argparse.ArgumentParser(description="Try to convert British quote style to American quote style. Quotes must already be typogrified using the `typogrify` tool. This script isn’t perfect; proofreading is required, especially near closing quotes near to em-dashes.")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("-f", "--force", action="store_true", help="force conversion of quote style")
	parser.add_argument("targets", metavar="TARGET", nargs="+", help="an XHTML file, or a directory containing XHTML files")
	args = parser.parse_args()

	for filename in se.get_target_filenames(args.targets, (".xhtml")):
		if args.verbose:
			print("Processing {} ...".format(filename), end="", flush=True)

		with open(filename, "r+", encoding="utf-8") as file:
			xhtml = file.read()
			new_xhtml = xhtml

			convert = True
			if not args.force:
				if se.typography.guess_quoting_style(xhtml) == "american":
					convert = False
					if args.verbose:
					 	print("")
					se.print_warning("File appears to already use American quote style, ignoring. Use --force to convert anyway.{}".format(" File: " + filename if not args.verbose else ""), args.verbose)

			if convert:
				new_xhtml = se.typography.convert_british_to_american(xhtml)

				if new_xhtml != xhtml:
					file.seek(0)
					file.write(new_xhtml)
					file.truncate()

		if convert and args.verbose:
			print(" OK")

	return 0

def build_images() -> int:
	parser = argparse.ArgumentParser(description="Build ebook covers and titlepages for a Standard Ebook source directory, and place the output in DIRECTORY/src/epub/images/.")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("directories", metavar="DIRECTORY", nargs="+", help="a Standard Ebooks source directory")
	args = parser.parse_args()

	for directory in args.directories:
		if args.verbose:
			print("Processing {} ...".format(directory))

		directory = os.path.abspath(directory)

		se_epub = SeEpub(directory)

		try:
			if args.verbose:
				print("\tBuilding cover.svg ...", end="", flush=True)

			se_epub.generate_cover_svg()

			if args.verbose:
				print(" OK")

			if args.verbose:
				print("\tBuilding titlepage.svg ...", end="", flush=True)

			se_epub.generate_titlepage_svg()

			if args.verbose:
				print(" OK")
		except se.SeException as ex:
			se.print_error(ex)
			return ex.code

	return 0

def clean() -> int:
	parser = argparse.ArgumentParser(description="Prettify and canonicalize individual XHTML or SVG files, or all XHTML and SVG files in a source directory.  Note that this only prettifies the source code; it doesn’t perform typography changes.")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("-s", "--single-lines", action="store_true", help="remove hard line wrapping")
	parser.add_argument("targets", metavar="TARGET", nargs="+", help="an XHTML or SVG file, or a directory containing XHTML or SVG files")
	args = parser.parse_args()

	for filename in se.get_target_filenames(args.targets, (".xhtml", ".svg", ".opf", ".ncx")):
		# If we're setting single lines, skip the colophon and cover/titlepage svgs, as they have special spacing
		if args.single_lines and (filename.endswith("colophon.xhtml") or filename.endswith("cover.svg") or filename.endswith("titlepage.svg")):
			continue

		if args.verbose:
			print("Processing {} ...".format(filename), end="", flush=True)

		try:
			se.formatting.format_xhtml_file(filename, args.single_lines, filename.endswith("content.opf"), filename.endswith("endnotes.xhtml"))
		except se.SeException as ex:
			se.print_error(ex, args.verbose)
			return ex.code

		if args.verbose:
			print(" OK")

	return 0

def titlecase() -> int:
	parser = argparse.ArgumentParser(description="Convert a string to titlecase.")
	parser.add_argument("-n", "--no-newline", dest="newline", action="store_false", help="don’t end output with a newline")
	parser.add_argument("titles", metavar="STRING", nargs="*", help="a string")
	args = parser.parse_args()

	lines = []

	if not sys.stdin.isatty():
		for line in sys.stdin:
			lines.append(line.rstrip("\r\n"))

	for line in args.titles:
		lines.append(line)

	for line in lines:
		if args.newline:
			print(se.formatting.titlecase(line))
		else:
			print(se.formatting.titlecase(line), end="")

	return 0
