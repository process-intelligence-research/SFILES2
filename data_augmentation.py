import os
import random

from SFILES2.Flowsheet_Class.flowsheet import Flowsheet

random.seed(1)


def canonical_to_noncanonical_sfile(sfiles, version: int = 2, sfiles_amount: int = 20, max_failed_attempts: int = 5):
    """Converts 1 SFILES into a random non-canonical SFILES, corresponding to the same graph
    Parameters
    ----------
    sfiles: string
        SFILES which should be augmented.
    version: integer
        SFILES version.
    sfiles_amount: integer
        Number of non-canonical SFILES created per input SFILES.
    max_failed_attempts: integer
        Maximum amount of consecutive failed attempts to create new unique non-canonical SFILES.
    Returns
    -------
    all_sfiles: set
        Set of augmented SFILES (including the input SFILES).
    """

    # Initialize flowsheet, SFILES set and counters.
    flowsheet = Flowsheet()
    all_sfiles = set()
    all_sfiles.add(sfiles)
    fail_counter = 0
    succes_counter = 0

    # Generate graph corresponding to provided SFILES.
    flowsheet.create_from_sfiles(sfiles, overwrite_nx=True)

    # Generate augmented (non-canonical) SFILES as long as required sfiles_amount and max fails is not reached.
    while succes_counter < sfiles_amount and fail_counter < max_failed_attempts:
        temp_set = set()
        try:
            flowsheet.convert_to_sfiles("v" + str(version), True, False)
            temp_set.add(flowsheet.sfiles)
        except AssertionError:
            print("Warning: Faulty SFILES created.")

        # Check if newly generated SFILES is already generated earlier or equal to the provided SFILES.
        if (temp_set | all_sfiles) == all_sfiles:
            fail_counter += 1
        else:
            all_sfiles.add(flowsheet.sfiles)
            succes_counter += 1
            fail_counter = 0

    return all_sfiles


def canonical_to_noncanonical_txt(version: int = 2, src: str = "dev_data", sfiles_amount: int = 20):
    """Converts a text file containing canonical SFILES (SFILES line-separated) into non-canonical SFILES and writes to
    results (canonical + noncanonical SFILES) to new text file.

    Parameters
    ----------
    version: integer
        SFILES version.
    src: string, default=dev_data.txt
        Source location of text file, which contains the SFILES for augmentation.
    sfiles_amount: integer
        Amount of non-canonical SFILES created per provided SFILES.
    """

    all_augmented_sfiles = set()
    with open(src) as file:
        for line in file:
            sfiles = line[:-1]
            augmented_sfiles = canonical_to_noncanonical_sfile(sfiles, version, sfiles_amount)
            all_augmented_sfiles = augmented_sfiles | all_augmented_sfiles

    base = os.path.splitext(src)[0]
    dst = base + "_augm" + ".txt"
    with open(dst, "w+") as file:
        for item in list(all_augmented_sfiles):
            file.write(f"{item}\n")


def non_canonical_tester(version: int = 2, src: str = "dev_data.txt", sfiles_amount: int = 10):
    """Tests the 'canonical_to_noncanonical_sfile' function: Canonical SFILES are converted to non-canonical SFILES and
    thereafter backconverted to canonical SFILES. Check if provided SFILES are equal to backconverted canonical SFILES.

    Parameters
    ----------
    version: integer
        SFILES version.
    src: string, default=dev_data.txt
        Source location of text file, which contains the SFILES for augmentation.
    sfiles_amount: integer
        Number of non-canonical SFILES created per original SFILES.

    Returns
    -------
    Percentage of correctly converted SFILES.
    """

    correct_augmentation = 0
    false_augmentation = 0

    with open(src) as file:
        for line in file:
            correct_counter = 0
            false_counter = 0

            # sfiles = line[:-2]
            sfiles = line[:-1]
            augmented_sfiles = canonical_to_noncanonical_sfile(sfiles, version, sfiles_amount)

            for item in augmented_sfiles:
                # Create flowsheet from non-canonical SFILES.
                flowsheet = Flowsheet()
                flowsheet.create_from_sfiles(item, overwrite_nx=True)
                # Convert flowsheet to canonical SFILES.
                try:
                    flowsheet.convert_to_sfiles("v" + str(version), True, True)
                except AssertionError:
                    print("Warning: Faulty SFILES created.")

                # Check if provided and re-converted to canonical SFILES are equal.
                if flowsheet.sfiles == sfiles:
                    correct_counter += 1
                else:
                    false_counter += 1
                    print(sfiles, "\n")
                    print(item, "\n")
                    print(flowsheet.sfiles, "\n")

            if correct_counter == len(augmented_sfiles):
                correct_augmentation += 1
            else:
                false_augmentation += 1
    return correct_augmentation / (correct_augmentation + false_augmentation) * 100
