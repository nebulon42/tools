#!/usr/bin/env python3

import sys
import argparse
import os
import types
import fnmatch
import subprocess
import tempfile
import shutil
import git
import psutil
import regex
import se
import se.formatting
import se.typography
import se.create_draft
from se.se_epub import SeEpub


def main() -> int:
	# Generate a list of available commands from all of the functions in this file.
	commands = []
	for item, value in globals().items():
		if isinstance(value, types.FunctionType) and item != "main" and not item.startswith("_"):
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

def compare_versions() -> int:
	parser = argparse.ArgumentParser(description="Use Firefox to render and compare XHTML files in an ebook repository. Run on a dirty repository to visually compare the repository’s dirty state with its clean state. If a file renders differently, copy screenshots of the new, original, and diff (if available) renderings into the current working directory. Diff renderings may not be available if the two renderings differ in dimensions. WARNING: DO NOT START FIREFOX WHILE THIS PROGRAM IS RUNNING!")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("-n", "--no-images", dest="copy_images", action="store_false", help="don’t copy diff images to the current working directory in case of difference")
	parser.add_argument("-i", "--include-common", dest="include_common_files", action="store_true", help="include commonly-excluded files like imprint, titlepage, and colophon")
	parser.add_argument("targets", metavar="TARGET", nargs="+", help="a directory containing XHTML files")
	args = parser.parse_args()

	firefox_path = shutil.which("firefox")
	compare_path = shutil.which("compare")

	# Check for some required tools.
	if firefox_path is None:
		se.print_error("Couldn’t locate firefox. Is it installed?")
		return se.MissingDependencyException.code

	if compare_path is None:
		se.print_error("Couldn’t locate compare. Is imagemagick installed?")
		return se.MissingDependencyException.code

	# Firefox won't start in headless mode if there is another Firefox process running; check that here.
	if "firefox" in (p.name() for p in psutil.process_iter()):
		se.print_error("Firefox is required, but it’s currently running. Stop all instances of Firefox and try again.")
		return se.FirefoxRunningException.code

	for target in args.targets:
		target = os.path.abspath(target)

		target_filenames = set()
		if os.path.isdir(target):
			for root, _, filenames in os.walk(target):
				for filename in fnmatch.filter(filenames, "*.xhtml"):
					if args.include_common_files or filename not in se.IGNORED_FILENAMES:
						target_filenames.add(os.path.join(root, filename))
		else:
			se.print_error("Target must be a directory: {}".format(target))
			continue

		if args.verbose:
			print("Processing {} ...\n".format(target), end="", flush=True)

		git_command = git.cmd.Git(target)

		if "nothing to commit" in git_command.status():
			se.print_error("Repo is clean. This script must be run on a dirty repo.", args.verbose)
			continue

		# Put Git's changes into the stash
		git_command.stash()

		with tempfile.TemporaryDirectory() as temp_directory_path:
			# Generate screenshots of the pre-change repo
			for filename in target_filenames:
				subprocess.run([firefox_path, "-screenshot", "{}/{}-original.png".format(temp_directory_path, os.path.basename(filename)), filename], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

			# Pop the stash
			git_command.stash("pop")

			# Generate screenshots of the post-change repo, and compare them to the old screenshots
			for filename in target_filenames:
				filename_basename = os.path.basename(filename)
				subprocess.run([firefox_path, "-screenshot", "{}/{}-new.png".format(temp_directory_path, filename_basename), filename], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

				output = subprocess.run([compare_path, "-metric", "ae", "{}/{}-original.png".format(temp_directory_path, filename_basename), "{}/{}-new.png".format(temp_directory_path, filename_basename), "{}/{}-diff.png".format(temp_directory_path, filename_basename)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode().strip()

				if output != "0":
					print("{}Difference in {}\n".format("\t" if args.verbose else "", filename), end="", flush=True)

					if args.copy_images:
						try:
							output_directory = "./" + os.path.basename(os.path.normpath(target)) + "_diff-output/"
							if not os.path.exists(output_directory):
								os.makedirs(output_directory)

							shutil.copy("{}/{}-new.png".format(temp_directory_path, filename_basename), output_directory)
							shutil.copy("{}/{}-original.png".format(temp_directory_path, filename_basename), output_directory)
							shutil.copy("{}/{}-diff.png".format(temp_directory_path, filename_basename), output_directory)
						except Exception:
							pass
	return 0

def create_draft() -> int:
	parser = argparse.ArgumentParser(description="Create a skeleton of a new Standard Ebook in the current directory.")
	parser.add_argument("-a", "--author", dest="author", required=True, help="the author of the ebook")
	parser.add_argument("-t", "--title", dest="title", required=True, help="the title of the ebook")
	parser.add_argument("-i", "--illustrator", dest="illustrator", help="the illustrator of the ebook")
	parser.add_argument("-r", "--translator", dest="translator", help="the translator of the ebook")
	parser.add_argument("-p", "--gutenberg-ebook-url", dest="pg_url", help="the URL of the Project Gutenberg ebook to download")
	parser.add_argument("-s", "--create-se-repo", dest="create_se_repo", action="store_true", help="initialize a new repository on the Standard Ebook server; Standard Ebooks admin powers required")
	parser.add_argument("-g", "--create-github-repo", dest="create_github_repo", action="store_true", help="initialize a new repository at the Standard Ebooks GitHub account; Standard Ebooks admin powers required; can only be used when --create-se-repo is specified")
	parser.add_argument("-e", "--email", dest="email", help="use this email address as the main committer for the local Git repository")
	args = parser.parse_args()

	if args.create_github_repo and not args.create_se_repo:
		se.print_error("--create-github-repo option specified, but --create-se-repo option not specified.")
		return se.InvalidInputException.code

	if args.pg_url and not regex.match("^https?://www.gutenberg.org/ebooks/[0-9]+$", args.pg_url):
		se.print_error("Project Gutenberg URL must look like: https://www.gutenberg.org/ebooks/<EBOOK-ID>")
		return se.InvalidInputException.code

	return se.create_draft.create_draft(args)

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
