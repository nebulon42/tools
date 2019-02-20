#!/usr/bin/env python3

import sys
import argparse
import os
import types
import subprocess
from subprocess import call
import tempfile
import shutil
import regex
import se
import se.formatting
import se.typography
import se.spelling
from se.se_epub import SeEpub


def main() -> int:
	"""
	Entry point for the main `se` executable.

	This function delegates subcommands (like `se typogrify`) to various functions within this module.

	Some more complex commands (like `create-draft` or `build` are broken out into their own files for
	readability and maintainability.
	"""

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
	"""
	Entry point for `se british2american`
	"""

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

def build() -> int:
	"""
	Entry point for `se build`

	The meat of this function is broken out into the build.py module for readability
	and maintainability.
	"""

	# Use an alias because se.build.build() is the same name as this.build()
	from se.build import build as se_build

	parser = argparse.ArgumentParser(description="Build compatible .epub and pure .epub3 ebooks from a Standard Ebook source directory.  Output is placed in the current directory, or the target directory with --output-dir.")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("-o", "--output-dir", dest="output_directory", metavar="DIRECTORY", type=str, help="a directory to place output files in; will be created if it doesn’t exist")
	parser.add_argument("-c", "--check", action="store_true", help="use epubcheck to validate the compatible .epub file; if --kindle is also specified and epubcheck fails, don’t create a Kindle file")
	parser.add_argument("-k", "--kindle", dest="build_kindle", action="store_true", help="also build an .azw3 file for Kindle")
	parser.add_argument("-b", "--kobo", dest="build_kobo", action="store_true", help="also build a .kepub.epub file for Kobo")
	parser.add_argument("-t", "--covers", dest="build_covers", action="store_true", help="output the cover and a cover thumbnail")
	parser.add_argument("-p", "--proof", action="store_true", help="insert additional CSS rules that are helpful for proofreading; output filenames will end in .proof")
	parser.add_argument("source_directory", metavar="DIRECTORY", help="a Standard Ebooks source directory")
	args = parser.parse_args()

	return se_build(args)

def build_images() -> int:
	"""
	Entry point for `se build-images`
	"""

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
	"""
	Entry point for `se clean`
	"""

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
	"""
	Entry point for `se compare-versions`
	"""

	import fnmatch
	import psutil
	import git

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
	"""
	Entry point for `se create-draft`

	The meat of this function is broken out into the create_draft.py module for readability
	and maintainability.
	"""

	# Use an alias because se.create_draft.create_draft() is the same name as this.create_draft()
	from se.create_draft import create_draft as se_create_draft

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

	return se_create_draft(args)

def dec2roman() -> int:
	"""
	Entry point for `se dec2roman`
	"""

	import roman

	parser = argparse.ArgumentParser(description="Convert a decimal number to a Roman numeral.")
	parser.add_argument("-n", "--no-newline", dest="newline", action="store_false", help="don’t end output with a newline")
	parser.add_argument("numbers", metavar="INTEGER", type=se.is_positive_integer, nargs="*", help="an integer")
	args = parser.parse_args()

	lines = []

	if not sys.stdin.isatty():
		for line in sys.stdin:
			lines.append(line.rstrip("\n"))

	for line in args.numbers:
		lines.append(line)

	for line in lines:
		if args.newline:
			print(roman.toRoman(int(line)))
		else:
			print(roman.toRoman(int(line)), end="")

	return 0

def extract_ebook() -> int:
	"""
	Entry point for `se extract-ebook`
	"""

	import zipfile
	from io import TextIOWrapper, BytesIO
	import magic
	from se.kindleunpack import kindleunpack

	parser = argparse.ArgumentParser(description="Extract an epub, mobi, or azw3 ebook into ./FILENAME.extracted/ or a target directory.")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("-d", "--destination", type=str, help="a target directory to extract into")
	parser.add_argument("targets", metavar="TARGET", nargs="+", help="an epub, mobi, or azw3 file")
	args = parser.parse_args()

	for target in args.targets:
		target = os.path.abspath(target)

		if args.verbose:
			print("Processing {} ...".format(target), end="", flush=True)

		if args.destination is None:
			extracted_path = os.path.basename(target) + ".extracted"
		else:
			extracted_path = args.destination

		if os.path.exists(extracted_path):
			se.print_error("Directory already exists: {}".format(extracted_path))
			return se.FileExistsException.code

		mime_type = magic.from_file(target)

		if "Mobipocket E-book" in mime_type:
			# kindleunpack uses print() so just capture that output here
			old_stdout = sys.stdout
			sys.stdout = TextIOWrapper(BytesIO(), sys.stdout.encoding)

			kindleunpack.unpackBook(target, extracted_path)

			# Restore stdout
			sys.stdout.close()
			sys.stdout = old_stdout
		elif "EPUB document" in mime_type:
			with zipfile.ZipFile(target, "r") as file:
				file.extractall(extracted_path)
		else:
			se.print_error("Couldn’t understand file type: {}".format(mime_type))
			return se.InvalidFileException.code

		if args.verbose:
			print(" OK")

	return 0

def find_mismatched_diacritics() -> int:
	"""
	Entry point for `se find-mismatched-diacritics`
	"""

	parser = argparse.ArgumentParser(description="Find words with mismatched diacritics in a set of XHTML files.  For example, `cafe` in one file and `café` in another.")
	parser.add_argument("targets", metavar="TARGET", nargs="+", help="an XHTML file, or a directory containing XHTML files")
	args = parser.parse_args()

	accented_words = set()
	mismatches = {}
	target_filenames = se.get_target_filenames(args.targets, (".xhtml"))

	for filename in target_filenames:
		with open(filename, "r", encoding="utf-8") as file:
			xhtml = file.read()

			decomposed_xhtml = unicodedata.normalize("NFKD", xhtml)

			pattern = regex.compile(r"\b\w*\p{M}\w*\b")
			for decomposed_word in pattern.findall(decomposed_xhtml):
				word = unicodedata.normalize("NFKC", decomposed_word)

				if len(word) > 2:
					accented_words.add(word.lower())

	# Now iterate over the list and search files for unaccented versions of the words
	if accented_words:
		for filename in target_filenames:
			with open(filename, "r", encoding="utf-8") as file:
				xhtml = file.read()

				for accented_word in accented_words:
					plain_word = regex.sub(r"\p{M}", "", unicodedata.normalize("NFKD", accented_word))

					pattern = regex.compile(r"\b" + plain_word + r"\b", regex.IGNORECASE)
					if pattern.search(xhtml) != None:
						mismatches[accented_word] = plain_word

	if mismatches:
		for accented_word, plain_word in sorted(mismatches.items()):
			print("{}, {}".format(accented_word, plain_word))

	return 0

def hyphenate() -> int:
	"""
	Entry point for `se hyphenate`
	"""

	parser = argparse.ArgumentParser(description="Insert soft hyphens at syllable breaks in XHTML files.")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("-l", "--language", action="store", help="specify the language for the XHTML files; if unspecified, defaults to the \"xml:lang\" or \"lang\" attribute of the root <html> element")
	parser.add_argument("-i", "--ignore-h-tags", action="store_true", help="don’t add soft hyphens to text in <h1-6> tags")
	parser.add_argument("targets", metavar="TARGET", nargs="+", help="an XHTML file, or a directory containing XHTML files")
	args = parser.parse_args()

	for filename in se.get_target_filenames(args.targets, (".xhtml")):
		if args.verbose:
			print("Processing {} ...".format(filename), end="", flush=True)

		se.typography.hyphenate_file(filename, args.language, args.ignore_h_tags)

		if args.verbose:
			print(" OK")

	return 0

def interactive_sr() -> int:
	"""
	Entry point for `se interactive-sr`
	"""

	parser = argparse.ArgumentParser(description="Use Vim to perform an interactive search and replace on a list of files. Use y/n/a to confirm (y) or reject (n) a replacement, or to replace (a)ll.")
	parser.add_argument("regex", metavar="REGEX", help="a Vim-flavored regex in the form of `/FIND/REPLACE/`; do not include flags; if using () backreferences, parentheses must be escaped")
	parser.add_argument("targets", metavar="TARGET", nargs="+", help="a file on which to perform the search and replace")
	args = parser.parse_args()

	# Check for required utilities
	vim_path = shutil.which("vim")

	if vim_path is None:
		se.print_error("Couldn’t locate vim. Is it installed?")
		return se.MissingDependencyException.code

	# 'set title' shows the filename in the terminal title
	# 'set eventignore-=Syntax' enables syntax highlighting in all files
	# 'wqa writes and quits all buffers
	# Full command: vim "+silent set title" "+silent bufdo set eventignore-=Syntax | %s${regex}gce | silent update" "+silent qa" "$@"
	call([vim_path, "+silent set title", "+silent bufdo set eventignore-=Syntax | %s{}gce | silent update".format(args.regex), "+silent qa"] + args.targets)

	return 0

def lint() -> int:
	"""
	Entry point for `se lint`
	"""

	from termcolor import colored

	parser = argparse.ArgumentParser(description="Check for various Standard Ebooks style errors.")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("-p", "--plain", action="store_true", help="print plain output")
	parser.add_argument("directories", metavar="DIRECTORY", nargs="+", help="a Standard Ebooks source directory")
	args = parser.parse_args()

	first_output = True

	for directory in args.directories:
		try:
			se_epub = SeEpub(directory)
		except se.SeException as ex:
			se.print_error(ex)
			return ex.code

		messages = se_epub.lint()

		table_data = []

		# Print a separator newline if more than one table is printed
		if not first_output and (args.verbose or messages):
			print("")
		elif first_output:
			first_output = False

		# Print the table header
		if args.verbose or (messages and len(args.directories) > 1):
			if args.plain:
				print(se_epub.directory)
			else:
				print(colored(se_epub.directory, "white", attrs=["reverse"]))

		# Print the table
		if messages:
			if args.plain:
				for message in messages:
					if message.is_submessage:
						print("\t" + message.text)
					else:
						label = "Manual Review:"

						if message.message_type == se.MESSAGE_TYPE_ERROR:
							label = "Error:"

						print(label, message.filename, message.text)

			else:
				for message in messages:
					if message.is_submessage:
						table_data.append([" ", "→", "{}".format(message.text)])
					else:
						alert = colored("Manual Review", "yellow")

						if message.message_type == se.MESSAGE_TYPE_ERROR:
							alert = colored("Error", "red")

						table_data.append([alert, message.filename, message.text])

				se.print_table(table_data, 2)

		if args.verbose and not messages:
			if args.plain:
				print("OK")
			else:
				table_data.append([colored("OK", "green", attrs=["reverse"])])

				se.print_table(table_data)

	return 0

def make_url_safe() -> int:
	"""
	Entry point for `se make-url-safe`
	"""

	parser = argparse.ArgumentParser(description="Make a string URL-safe.")
	parser.add_argument("-n", "--no-newline", dest="newline", action="store_false", help="don’t end output with a newline")
	parser.add_argument("strings", metavar="STRING", nargs="*", help="a string")
	args = parser.parse_args()

	lines = []

	if not sys.stdin.isatty():
		for line in sys.stdin:
			lines.append(line.rstrip("\n"))

	for line in args.strings:
		lines.append(line)

	for line in lines:
		if args.newline:
			print(se.formatting.make_url_safe(line))
		else:
			print(se.formatting.make_url_safe(line), end="")

	return 0

def titlecase() -> int:
	"""
	Entry point for `se titlecase`
	"""

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
