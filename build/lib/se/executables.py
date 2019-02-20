#!/usr/bin/env python3

import sys
import argparse
import types
import se
import se.typography

COMMANDS = []

def main() -> int:
	for item, value in globals().items():
		if isinstance(value, types.FunctionType) and item != "main":
			COMMANDS.append(item)

	parser = argparse.ArgumentParser(description="The entry point for the Standard Ebooks toolset.")
	parser.add_argument("command", metavar="COMMAND", choices=COMMANDS, help="\n".join(COMMANDS))
	parser.add_argument("arguments", metavar="ARGS", nargs="*", help="arguments for the subcommand")
	args = parser.parse_args(sys.argv[1:2])

	# Remove the command name from the list of passed args
	sys.argv.pop(1)

	print(globals())

	# Change the command name so that argparse instances in child functions report the correct command on help/error
	sys.argv[0] = args.command

	# Now execute the command
	return globals()[args.command]()

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
