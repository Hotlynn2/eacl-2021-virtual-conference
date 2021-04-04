import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from pathlib import Path
from typing import List, Dict, Tuple

import pandas as pd
import pytz
from openpyxl import load_workbook
from openpyxl.styles import numbers
from pybtex import database
from pylatexenc.latex2text import LatexNodes2Text
from ftfy import fix_text

import ruamel
from ruamel import yaml

from scripts.dataentry.paths import (
    download_accepted_submissions,
    PATH_ACCEPTED_SUBMISSIONS,
    download_programme,
    PATH_PROGRAMME,
)

PATH_TO_MAIN_PROCEEDINGS = Path(
    r"D:\eacl\data\papers\proceedings\final"
)  # Extract final.tgz for this
PATH_TO_MAIN_BIB = Path(r"D:\eacl\data\papers\proceedings\cdrom\2021.eacl-main.0.bib")

PATH_TO_DEMO_PROCEEDINGS = Path(r"D:\eacl\data\demos\proceedings\final")
PATH_TO_DEMO_BIB = Path(r"D:\eacl\data\demos\proceedings\cdrom\2021.eacl-demos.0.bib")


def get_mappings_for_main_papers() -> Tuple[Dict[str, str], Dict[str, str]]:
    """ Returns a dict that maps submission id to track name and submission id to paper type """

    download_accepted_submissions()

    df = pd.read_csv(
        PATH_ACCEPTED_SUBMISSIONS,
        names=[
            "submission_id",
            "presentation_type",
            "paper_type",
            "track",
            "title",
            "abstract",
            "authors",
        ],
    )
    track_mapping = {
        str(row["submission_id"]): row["track"] for _, row in df.iterrows()
    }
    paper_type_mapping = {
        str(row["submission_id"]): row["paper_type"] for _, row in df.iterrows()
    }

    return track_mapping, paper_type_mapping


def get_paper_urls_from_bib(path_to_bib: Path) -> Dict[str, str]:
    """ Opens the bibliography in the proceedings and gets ACL anthology paper URLs from there. """
    with path_to_bib.open() as f:
        bib = database.parse_file(f)

    urls = {}

    for entry in bib.entries.values():
        title = entry.fields["title"].replace("\\", "")
        title = LatexNodes2Text().latex_to_text(title)
        title = fix_text(title).strip()

        urls[title] = entry.fields["url"]

    return urls


def get_sliveslive_id_mapping():
    pass


def parse_proceedings(
    path_to_proceedings: Path,
    path_to_bib: Path,
    tracks_dict: Dict[str, str],
    papertypes: Dict[str, str],
    slideslives_dict: Dict[str, str],
    has_presentation: bool = True,
) -> pd.DataFrame:
    title_to_url = get_paper_urls_from_bib(path_to_bib)

    UIDs = []
    titles = []
    authors = []
    abstracts = []
    keywords = []
    tracks = []
    paper_types = []
    pdf_urls = []
    presentation_ids = []

    for paper_folder in path_to_proceedings.iterdir():
        uid = paper_folder.name
        metadata_path = paper_folder / f"{uid}_metadata.txt"

        with metadata_path.open() as f:
            submission_number = str(f.readline().split("#=%=#")[1]).strip()
            title = f.readline().split("#=%=#")[1].strip()
            title = LatexNodes2Text().latex_to_text(title)
            title = fix_text(title).strip()

            for line in f:
                if line.startswith("Abstract"):
                    break

            abstract = line.split("#==#")[1].strip()

            for line in f:
                if line.startswith("Author"):
                    break

                abstract += " " + line.strip()

            raw_authors = []

            author_fields = defaultdict(dict)
            for line in chain([line], f):
                line = line.strip()
                if len(line) == 0:
                    break

                assert line.startswith("Author{"), line

                matcher = re.match(r"Author\{(\d+)\}\{(.+?)\}#=%=#(.+)", line)
                author_no = matcher.group(1)
                field_name = matcher.group(2)
                value = matcher.group(3)
                author_fields[author_no][field_name] = value

            for author_data in author_fields.values():
                raw_authors.append(
                    f"{author_data['Firstname']} {author_data.get('Lastname', '')}".strip()
                )

        UIDs.append(submission_number)
        titles.append(title)
        authors.append("|".join(raw_authors))
        abstracts.append(abstract)
        keywords.append("")
        tracks.append(
            tracks_dict.get(submission_number, tracks_dict[submission_number])
        )
        paper_types.append(papertypes[submission_number])
        pdf_urls.append(title_to_url[title])

        if has_presentation:
            # TODO: Fix me
            # slideslive_id = slideslives_dict[submission_number]
            slideslive_id = f"slideslive#{submission_number}"
            presentation_ids.append(submission_number)

    data = {
        "UID": UIDs,
        "title": titles,
        "authors": authors,
        "abstract": abstracts,
        "keywords": keywords,
        "track": tracks,
        "paper_type": paper_types,
        "pdf_url": pdf_urls,
    }

    columns = [
        "UID",
        "title",
        "authors",
        "abstract",
        "keywords",
        "track",
        "paper_type",
        "pdf_url",
    ]
    if has_presentation:
        data["presentation_id"] = presentation_ids
        columns.append("presentation_id")

    df = pd.DataFrame(data, columns=columns)

    return df


def create_main_papers():
    track_mapping, paper_types = get_mappings_for_main_papers()
    main_papers = parse_proceedings(
        PATH_TO_MAIN_PROCEEDINGS, PATH_TO_MAIN_BIB, track_mapping, paper_types, {}
    )

    main_papers["UID"] = main_papers["UID"].apply(lambda uid: f"main.{uid}")
    main_papers.to_csv("yamls/main_papers.csv", index=False)


def create_demo_papers():
    demo_track_dict = defaultdict(lambda: "System Demonstrations")
    demo_papertype_dict = defaultdict(lambda: "demo")
    demo_papers = parse_proceedings(
        PATH_TO_DEMO_PROCEEDINGS,
        PATH_TO_DEMO_BIB,
        demo_track_dict,
        demo_papertype_dict,
        {},
        has_presentation=False,
    )
    demo_papers["demo_url"] = ""
    demo_papers["UID"] = "demo." + demo_papers["UID"]

    # demo_papers = pd.read_csv("demo_papers_keywords.csv")
    # demo_papers = enrich_demos(demo_papers)

    demo_papers.to_csv("yamls/demo_papers.csv", index=False)


def generate_paper_sessions():
    download_programme()
    wb = load_workbook(PATH_PROGRAMME)

    ws_programme = wb.worksheets[0]
    ws_programme.delete_rows(1, 1)
    ws_programme.delete_rows(128, 10000)

    for row in ws_programme:
        cell = row[1]
        cell.number_format = numbers.FORMAT_TEXT

    programme = pd.DataFrame(
        ws_programme.values,
        columns=[
            "Day",
            "Time (CEST)",
            "Oral Session",
            "Session Chair",
            "Poster session",
            "Paper ID",
            "Track",
            "Authors",
            "Paper Title",
        ],
    )

    # Mappings

    result = {}

    # We want to find out which sessions run in parallel to give them the same block id
    block_id = 1
    time_to_block_id = {}
    time_to_sub_id = defaultdict(int)

    # Add oral
    oral_programme = programme[programme["Paper ID"].apply(lambda x: isinstance(x, float))]

    for session_name, group in oral_programme.groupby("Oral Session"):
        start_time, end_time = programme_time(group.iloc[0])

        entry = {
            "start_time": start_time,
            "end_time": end_time,
            "name": session_name,
            "long_name": map_session_name(session_name),
            "papers": [
                f"main.{int(e)}" for e in group["Paper ID"] if e != "TACL" and e != "CL"
            ],
        }

        if start_time not in time_to_block_id:
            time_to_block_id[start_time] = block_id
            block_id += 1

        b_id = time_to_block_id[start_time]
        s_id = time_to_sub_id[start_time]
        time_to_sub_id[start_time] += 1

        result[f"z{b_id}{chr(ord('A') + s_id)}"] = entry

    # Add posters

    poster_programme = programme[~programme["Poster session"].isnull()]
    poster_session_to_time = {
        re.sub(r"\s+", " ", row["Poster session"]): programme_time(row)
        for _, row in poster_programme.iterrows()
    }

    ws_posters = wb.worksheets[1]
    ws_posters.delete_rows(1, 1)

    poster_sessions = pd.DataFrame(
        ws_posters.values,
        columns=["Day", "Poster Slot", "Paper ID", "Track", "Paper Title", "Authors"],
    ).dropna(how="all")

    for session_name, group in poster_sessions.groupby("Poster Slot"):
        start_time, end_time = poster_session_to_time[session_name]
        entry = {
            "start_time": start_time,
            "end_time": end_time,
            "name": session_name,
            "long_name": map_session_name(session_name),
            "papers": [
                f"main.{int(e)}" for e in group["Paper ID"] if e != "TACL" and e != "CL"
            ],
        }

        if start_time not in time_to_block_id:
            time_to_block_id[start_time] = block_id
            block_id += 1

        b_id = time_to_block_id[start_time]
        s_id = time_to_sub_id[start_time]
        time_to_sub_id[start_time] += 1

        result[f"g{b_id}{chr(ord('A') + s_id)}"] = entry



    class NoAliasDumper(ruamel.yaml.RoundTripDumper):
        def ignore_aliases(self, data):
            return True

    with open("yamls/paper_sessions.yml", "w") as f:
        yaml.dump(result, f, Dumper=NoAliasDumper)


def programme_time(row: Dict[str, str]) -> Tuple[datetime, datetime]:
    """ Parses the times from the programme sheet, e.g. Apr 21	14-15 to begin and end times. """
    day = row["Day"].to_pydatetime()
    t = row["Time (CEST)"]

    if isinstance(t, datetime):
        begin = t.month
        end = t.day
    else:
        begin, end = t.split("-")
    begin, end = int(begin), int(end)

    timezone = pytz.timezone("Europe/Berlin")

    time_begin = timezone.localize(day.replace(hour=begin))
    time_end = timezone.localize(day.replace(hour=end))

    return time_begin, time_end


def map_session_name(short_name: str) -> str:

    name_mapping = {
        "DIA": "Dialogue and Interactive Systems",
        "DOC 1": "Document Analysis and Text Classification",
        "INTERPRET": "Interpretability and Anlysis of NLP Models",
        "CSS": "Computational Social Choice and Social Media",
        "GEN": "Natural Language Generation",
        "IR/QA": "Information Retrieval and Question Answering",
        "ML": "Machine Learning in NLP",
        "SYNTAX": "Tagging, Chunking, Syntax and Parsing",
        "DISCO": "Discourse and Pragmatics",
        "IE": "Information Extraction",
        "LRE": "Language Resources and Evaluation",
        "MT": "Machine Translation",
        "GROUND": "Natural Language Grounding",
        "MULTI": "Multilinguality",
        "SEM-Lex": "Lexical Semantics",
        "LING": "Linguistic Theories, Cognitive Modeling and Psycholinguistics",
        "SENTIMENT": "Sentiment Analysis, Stylistic Analysis and Argument Mining",
        "SRW": "Student Research Workshop",
        "MULTILING": "Multilinguality",
        "MORPH": "Phonology, Morphology and Word Segmentation",
        "SEM-Sent": "Sentence-Level Semantics",
        "DISCO-SUM": "Discourse and Summarization",
        "DIA-GEN": "Dialogue and Interactive Systems, Natural language Generation and Summarization",
        "SOCIAL 1": "Computational Social Choice and Social Media, Sentiment Analysis, Stylisting Analysis and Argumen Mining",
        "SEM 1": "Lexical Semantics, Sentence-Level Semantics, and Natural Language Grrounding",
        "APPS 2": "Information Extraction, Information Retrieval, Text Categorization and Question Answering",
        "LING 2": "Morphology and Syntax, Linguistic and Cognitive Modeling, Interpretability and Analysis ",
        "ML-GREEN-LRE  2": "Machine Learning, Green and Sustainbale NLP, Language Resources and Evaluation",
        "MT-MULTI 3": "Machine Translation and Multilnguality",
        "ML-LRE-MISC 3": "Machine Learning, Language Resources and Evaluation, Miscellenous NLP ",
        "MT-LRE  1": "Machine Translation, Language Resources and Evaluation",
    }
    if short_name not in name_mapping:
        return short_name.strip()

    return name_mapping[short_name].strip()


if __name__ == "__main__":
    # create_main_papers()
    # create_demo_papers()

    generate_paper_sessions()
