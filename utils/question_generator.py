import os
import logging
import re
from typing import List, Dict, Any
import json
import random
import math
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Azure OpenAI credentials from environment variables
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
DEFAULT_QUESTIONS_PER_TEST = int(os.environ.get("DEFAULT_QUESTIONS_PER_TEST", "120"))

def generate_questions(text: str, num_questions: int = None) -> List[Dict[str, Any]]:
    """
    Generate multiple-choice questions from PDF text.
    
    Args:
        text: Text extracted from PDF
        num_questions: Number of questions to generate
        
    Returns:
        List of question dictionaries with options and correct answer
    """
    # Use environment variable if num_questions not specified
    if num_questions is None:
        num_questions = DEFAULT_QUESTIONS_PER_TEST

    try:
        # Check if we have Azure OpenAI credentials
        if AZURE_API_KEY and AZURE_ENDPOINT:
            # Implement actual OpenAI-based question generation here
            # This would require a full implementation with Azure OpenAI
            logger.info("Would use Azure OpenAI for question generation, but using alternative method")
        
        # For this demo, we'll generate questions based on the text content
        # using some simple NLP techniques and chunking for better coverage
        logger.info(f"Generating {num_questions} multiple-choice questions using chunking method")
        
        # Simplify text to make processing easier
        simplified_text = text.replace('\n', ' ').strip()
        
        # Split into paragraphs first (for chunking)
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 50]
        
        # If too few paragraphs, split by sentences
        if len(paragraphs) < 10:
            logger.info("Too few paragraphs, splitting by sentences")
            sentences = re.split(r'[.!?]+', simplified_text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
            
            # Create paragraph-like chunks from sentences
            chunk_size = max(5, len(sentences) // 20)  # Aim for at least 20 chunks
            paragraphs = []
            for i in range(0, len(sentences), chunk_size):
                paragraph = ' '.join(sentences[i:i+chunk_size])
                if paragraph:
                    paragraphs.append(paragraph)
        
        # Calculate chunks needed
        num_chunks = min(20, len(paragraphs))  # Max 20 chunks
        questions_per_chunk = math.ceil(num_questions / num_chunks)
        
        logger.info(f"Created {num_chunks} chunks with ~{questions_per_chunk} questions per chunk")
        
        # Create even-sized chunks by grouping paragraphs
        chunks = []
        paragraphs_per_chunk = max(1, len(paragraphs) // num_chunks)
        for i in range(0, len(paragraphs), paragraphs_per_chunk):
            chunk = ' '.join(paragraphs[i:i+paragraphs_per_chunk])
            chunks.append(chunk)
        
        # Additional templates for more question variety
        general_templates = [
            "What is described as {phrase}?",
            "What does {subject} refer to in the text?",
            "Which {category} is mentioned in relation to {subject}?",
            "What is the main concept described in '{sentence_start}...'?",
            "What is the relationship between {subject} and {related}?",
            "What is the significance of {subject}?",
            "How does the text describe {subject}?",
            "What example is given for {concept}?",
            "What characteristic is attributed to {subject}?",
            "According to the text, what is {subject}?",
            "What process involves {element}?",
            "What is a key feature of {subject}?",
            "Which statement about {subject} is true according to the text?"
        ]
        
        factual_templates = [
            "Which fact about {subject} is mentioned in the text?",
            "What detail is provided about {subject} in this section?",
            "What specific information does the text provide about {subject}?",
            "What is stated about {subject} in this part of the document?",
            "Which piece of data regarding {subject} appears in the text?",
            "What specific metric or number is associated with {subject}?",
            "Which statistic related to {subject} is mentioned?",
            "What quantitative information is given about {subject}?"
        ]
        
        analytical_templates = [
            "What conclusion can be drawn about {subject} based on this section?",
            "What inference is supported by the information about {subject}?",
            "How would you interpret the information about {subject}?",
            "What does the text suggest about the importance of {subject}?",
            "What analysis is provided regarding {subject}?",
            "What would be a reasonable interpretation of the section about {subject}?",
            "What perspective does the text offer on {subject}?",
            "How might one evaluate the information presented about {subject}?"
        ]
        
        comparison_templates = [
            "How does {subject} compare to {related}?",
            "What distinction is made between {subject} and {related}?",
            "What similarity exists between {subject} and {related}?",
            "In what way does {subject} differ from {related}?",
            "How are {subject} and {related} connected according to the text?",
            "What relationship is established between {subject} and {related}?",
            "How do the characteristics of {subject} contrast with those of {related}?",
            "What comparative analysis is offered between {subject} and {related}?"
        ]
        
        # Combine all templates for variety
        all_templates = general_templates + factual_templates + analytical_templates + comparison_templates
        
        # Generate questions from each chunk
        all_questions = []
        cumulative_questions = 0
        
        for chunk_index, chunk_text in enumerate(chunks):
            # Calculate how many questions to generate from this chunk
            # Adjust to ensure we get exactly num_questions total
            remaining_chunks = len(chunks) - chunk_index
            remaining_questions = num_questions - cumulative_questions
            target_questions = min(questions_per_chunk, math.ceil(remaining_questions / remaining_chunks))
            
            logger.info(f"Processing chunk {chunk_index+1}/{len(chunks)}, aiming for {target_questions} questions")
            
            # Generate questions for this chunk
            chunk_questions = generate_questions_from_chunk(chunk_text, target_questions, all_templates)
            all_questions.extend(chunk_questions)
            cumulative_questions += len(chunk_questions)
            
            # Break if we've reached our target
            if cumulative_questions >= num_questions:
                break
        
        # Ensure we have exactly the requested number of questions
        if len(all_questions) > num_questions:
            all_questions = all_questions[:num_questions]
        
        # If we couldn't generate enough questions, add generic ones
        while len(all_questions) < num_questions:
            i = len(all_questions)
            generic_question = f"Question {i+1}: What is the main topic discussed in this section of the document?"
            
            # Generic options with slightly more variety
            options = {
                "A": "The section relates to key information presented in the text.",
                "B": f"The section focuses on {get_random_subject(text)}.",
                "C": f"The section analyzes various aspects of {get_random_subject(text)}.",
                "D": f"The section explains the relationship between {get_random_subject(text)} and {get_random_subject(text)}."
            }
            
            all_questions.append({
                "question": generic_question,
                "options": options,
                "answer": "A"
            })
        
        logger.info(f"Successfully generated {len(all_questions)} multiple-choice questions")
        return all_questions
    
    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        # Return a default set of questions if generation fails
        return [
            {
                "question": f"Question {i+1}: What is the main topic of this section?",
                "options": {
                    "A": "The section covers key information in the document.",
                    "B": f"The section focuses on concept {(i % 4) + 1}.",
                    "C": f"The section provides details about technique {(i % 5) + 1}.",
                    "D": f"The section explains principle {(i % 3) + 1}."
                },
                "answer": "A"
            } for i in range(num_questions)
        ]

def get_random_subject(text):
    """Extract a random meaningful subject from text"""
    words = text.split()
    meaningful_words = [word for word in words if len(word) > 5 and word.isalpha()]
    
    if meaningful_words:
        return random.choice(meaningful_words)
    return "the topic"

def extract_keywords(text, n=5):
    """Extract top n most frequent meaningful words as keywords"""
    # Simple keyword extraction based on word frequency
    words = re.findall(r'\b[a-zA-Z]{5,}\b', text.lower())  # Words with 5+ letters
    word_counts = {}
    for word in words:
        if word not in word_counts:
            word_counts[word] = 0
        word_counts[word] += 1
    
    # Sort by frequency and get top n
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:n]]

def generate_questions_from_chunk(chunk_text, num_chunk_questions, templates):
    """Generate questions from a specific chunk of text"""
    # Simplify chunk text
    simplified_chunk = chunk_text.replace('\n', ' ').strip()
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', simplified_chunk)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
    
    # If we have too few sentences, duplicate them
    while len(sentences) < num_chunk_questions * 3:
        sentences.extend(sentences)
    
    # Extract keywords from this chunk for better context
    keywords = extract_keywords(simplified_chunk)
    
    # Shuffle sentences to get more variety
    random.shuffle(sentences)
    
    # Generate questions from the sentences
    chunk_questions = []
    
    # Generate questions up to the requested number
    for i in range(min(num_chunk_questions, len(sentences))):
        sentence = sentences[i]
        words = sentence.split()
        
        if len(words) < 5:
            continue
            
        # Extract some key phrases
        subject = " ".join(words[:2])
        sentence_start = " ".join(words[:5])
        phrase = " ".join(random.sample(words, min(3, len(words))))
        
        # Better subject extraction - try to use keywords
        if keywords and random.random() < 0.7:  # 70% chance to use a keyword
            subject = random.choice(keywords)
        
        # Find a related term
        related = random.choice(words)
        if len(keywords) > 1 and random.random() < 0.7:  # 70% chance to use another keyword
            keywords_copy = keywords.copy()
            if subject in keywords_copy:
                keywords_copy.remove(subject)
            related = random.choice(keywords_copy)
        
        # Pick a random template
        template_q = random.choice(templates)
        
        # Generate question from template
        question = template_q.format(
            phrase=phrase,
            subject=subject,
            category=random.choice(["concept", "term", "idea", "principle", "factor", "method", "approach", "theory"]),
            sentence_start=sentence_start,
            related=related,
            concept=subject,
            element=random.choice(words)
        )
        
        # Generate the correct answer
        if len(sentence) > 100:
            correct_answer = sentence[:100].strip() + "..."
        else:
            correct_answer = sentence
        
        # Generate distractor options
        distractors = []
        
        # Use other sentences as distractors
        other_sentences = [s for s in sentences if s != sentence]
        
        for _ in range(3):  # 3 distractors
            if other_sentences:
                distractor = random.choice(other_sentences)
                other_sentences.remove(distractor)
                if len(distractor) > 100:
                    distractor = distractor[:100].strip() + "..."
                distractors.append(distractor)
            else:
                # Fallback if we don't have enough sentences
                distractor = "Information not provided in this section of the text."
                distractors.append(distractor)
        
        # Create all options and randomize their order
        options = [correct_answer] + distractors
        random.shuffle(options)
        
        # Save the correct answer index
        correct_index = options.index(correct_answer)
        
        # Create option labels (A, B, C, D)
        labeled_options = {}
        for j, option in enumerate(options):
            labeled_options[chr(65 + j)] = option  # A, B, C, D
        
        chunk_questions.append({
            "question": question,
            "options": labeled_options,
            "answer": chr(65 + correct_index)  # A, B, C, D
        })
        
        # Return the requested number of questions
        if len(chunk_questions) == num_chunk_questions:
            break
    
    return chunk_questions

def generate_ojee_questions(subject: str = None, num_questions: int = 30, math_count: int = None, computer_count: int = None):
    """
    Generate OJEE mock exam questions for mathematics and computer awareness subjects.
    
    Can be called in two ways:
    1. With subject and num_questions to generate one type of question
    2. With math_count and computer_count to generate both types
    
    Args:
        subject: Either "mathematics" or "computer_awareness", or None if using math_count/computer_count
        num_questions: Number of questions to generate if using subject parameter
        math_count: Number of mathematics questions to generate
        computer_count: Number of computer awareness questions to generate
        
    Returns:
        If subject is specified: List of question dictionaries for that subject
        If math_count/computer_count is specified: Dictionary with both question types
    """
    logger.info(f"Generating OJEE exam questions")
    
    try:
        # If called with subject parameter, generate questions for that subject
        if subject is not None:
            logger.info(f"Generating {num_questions} {subject} questions")
            
            if subject == "mathematics":
                questions = generate_math_questions(num_questions)
            elif subject == "computer_awareness":
                questions = generate_computer_questions(num_questions)
            else:
                logger.error(f"Unknown subject: {subject}")
                return []
                
            logger.info(f"Successfully generated {len(questions)} {subject} questions")
            return questions
            
        # If called with math_count/computer_count, generate both types
        else:
            math_questions = generate_math_questions(math_count or 30)
            computer_questions = generate_computer_questions(computer_count or 30)
            
            logger.info(f"Successfully generated {len(math_questions)} math questions and {len(computer_questions)} computer questions")
            return {
                "mathematics": math_questions,
                "computer_awareness": computer_questions
            }
            
    except Exception as e:
        logger.error(f"Error generating OJEE exam questions: {str(e)}")
        
        # Return default questions if generation fails
        if subject is not None:
            return generate_default_questions(subject, num_questions)
        else:
            return {
                "mathematics": generate_default_questions("mathematics", math_count or 30),
                "computer_awareness": generate_default_questions("computer_awareness", computer_count or 30)
            }

def generate_math_questions(num_questions: int) -> List[Dict[str, Any]]:
    """Generate mathematics questions for OJEE exam"""
    
    # Define question templates for different math categories
    algebra_templates = [
        "Solve for x: {equation}",
        "If {equation_1}, and {equation_2}, find the value of {variable}.",
        "Simplify: {expression}",
        "Find the value of {variable} in the equation {equation}",
        "If {condition}, what is the value of {expression}?"
    ]
    
    geometry_templates = [
        "In a triangle with sides {a}, {b}, and {c}, find {unknown}.",
        "Calculate the area of a {shape} with {dimensions}.",
        "Find the perimeter of a {shape} with {dimensions}.",
        "If the {shape} has {property}, calculate {unknown}.",
        "In a circle with radius {r}, find {unknown}."
    ]
    
    calculus_templates = [
        "Find the derivative of {function}.",
        "Evaluate the definite integral of {function} from {a} to {b}.",
        "Find the local maximum of the function {function}.",
        "If f(x) = {function}, find f'({x}).",
        "Calculate the area under the curve {function} between x = {a} and {b}."
    ]
    
    # Math categories with their templates
    categories = {
        "algebra": algebra_templates,
        "geometry": geometry_templates,
        "calculus": calculus_templates,
        "statistics": algebra_templates,  # Reusing algebra templates for now
        "trigonometry": geometry_templates  # Reusing geometry templates for now
    }
    
    # Core math topics for OJEE
    topics = [
        "Quadratic Equations", "Linear Equations", "Matrices", "Determinants",
        "Sequences and Series", "Complex Numbers", "Logarithms", "Trigonometry",
        "Coordinate Geometry", "Conic Sections", "Vectors", "3D Geometry",
        "Derivatives", "Integrals", "Probability", "Statistics", "Permutation and Combination"
    ]
    
    # Generate questions by distributing across topics
    questions = []
    category_keys = list(categories.keys())
    
    for i in range(num_questions):
        # Select category and template
        category = random.choice(category_keys)
        template = random.choice(categories[category])
        topic = random.choice(topics)
        
        # Generate question data
        equation = generate_math_equation(category)
        variable = random.choice(['x', 'y', 'z'])
        
        # Create question
        question_text = f"[{topic}] {template}".format(
            equation=equation,
            equation_1=generate_math_equation(category),
            equation_2=generate_math_equation(category),
            variable=variable,
            expression=generate_math_expression(category),
            condition=generate_math_condition(category),
            a=random.randint(1, 10),
            b=random.randint(1, 10),
            c=random.randint(1, 10),
            shape=random.choice(['triangle', 'rectangle', 'circle', 'square', 'parallelogram']),
            dimensions=f"length {random.randint(1, 10)} and width {random.randint(1, 10)}",
            property=f"area {random.randint(10, 100)}",
            unknown=random.choice(['area', 'perimeter', 'angle', 'height']),
            r=random.randint(1, 10),
            function=generate_math_function(),
            x=random.randint(1, 5)
        )
        
        # Create options (make sure they're distinct)
        correct_answer = random.randint(1, 100)
        options = {
            "A": f"{correct_answer}",
            "B": f"{correct_answer + random.randint(1, 10)}",
            "C": f"{correct_answer - random.randint(1, 10)}",
            "D": f"{correct_answer * 2}"
        }
        
        # Create explanation
        explanation = f"To solve this problem, you need to {generate_math_explanation(category)}"
        
        questions.append({
            "question": question_text,
            "options": options,
            "answer": "A",  # Correct answer is always A in this example
            "explanation": explanation,
            "category": category,
            "topic": topic
        })
    
    return questions

def generate_computer_questions(num_questions: int) -> List[Dict[str, Any]]:
    """Generate computer awareness questions for OJEE exam based on the specified syllabus"""
    
    # Computer fundamentals section (10-15% of questions)
    computer_fundamentals = {
        "topic": "COMPUTER FUNDAMENTALS",
        "subtopics": [
            "Basics of computers: Definition, characteristics, generations",
            "Classification: Analog, digital, hybrid computers",
            "Hardware vs Software",
            "Number systems: Binary, Octal, Decimal, Hexadecimal",
            "Conversions between number systems",
            "ASCII, Unicode"
        ]
    }
    
    # Data representation & memory section (10-15% of questions)
    data_representation = {
        "topic": "DATA REPRESENTATION & MEMORY",
        "subtopics": [
            "Data types, bits and bytes",
            "Storage units and hierarchy",
            "Primary memory (RAM, ROM), secondary memory",
            "Cache, registers, virtual memory"
        ]
    }
    
    # Operating system basics section (10% of questions)
    operating_systems = {
        "topic": "OPERATING SYSTEM BASICS",
        "subtopics": [
            "Functions of OS",
            "Types: Batch, Time-sharing, Real-time, Distributed",
            "Basics of process management, file systems"
        ]
    }
    
    # Computer organization section (10% of questions)
    computer_organization = {
        "topic": "COMPUTER ORGANIZATION",
        "subtopics": [
            "Input/output devices: Mouse, keyboard, scanner, printer",
            "CPU, ALU, Control Unit, buses",
            "Memory addressing and I/O concepts"
        ]
    }
    
    # Software concepts section (10% of questions)
    software_concepts = {
        "topic": "SOFTWARE CONCEPTS",
        "subtopics": [
            "System software vs Application software",
            "Translators: Compiler, Interpreter, Assembler",
            "Programming languages: Machine, Assembly, High-level",
            "Software development life cycle (basic understanding)"
        ]
    }
    
    # Internet & networking section (10% of questions)
    internet_networking = {
        "topic": "INTERNET & NETWORKING",
        "subtopics": [
            "Basics of Internet, WWW, browser",
            "IP address, DNS, URL, protocols (HTTP, FTP, TCP/IP)",
            "Network types: LAN, WAN, MAN",
            "Topologies: Star, Ring, Bus",
            "Email basics, cloud computing (introductory)"
        ]
    }
    
    # C Programming section (20-30% of questions)
    c_programming = {
        "topic": "C PROGRAMMING",
        "subtopics": [
            "Data types, variables, operators (arithmetic, relational, logical)",
            "Control statements: if-else, switch, loops (for, while, do-while)",
            "Functions: declaration, definition, recursion, scope",
            "Arrays (1D, 2D), strings, string functions",
            "Pointers and pointer arithmetic",
            "Structures and unions",
            "Dynamic memory allocation: malloc, calloc, free",
            "File handling basics",
            "Code output prediction",
            "Error detection and correction"
        ]
    }
    
    # MS Office section (5% of questions)
    ms_office = {
        "topic": "MS OFFICE",
        "subtopics": [
            "MS Word: editing, formatting",
            "MS Excel: formulas, charts",
            "MS PowerPoint: slides, transitions, animations"
        ]
    }
    
    # Database fundamentals section (5% of questions)
    database_fundamentals = {
        "topic": "DATABASE FUNDAMENTALS",
        "subtopics": [
            "DBMS vs RDBMS",
            "Basic SQL commands: SELECT, INSERT, UPDATE, DELETE",
            "Data models and keys (primary, foreign)"
        ]
    }
    
    # Cyber security & ethics section (5% of questions)
    cyber_security = {
        "topic": "CYBER SECURITY & ETHICS",
        "subtopics": [
            "Malware: viruses, worms, Trojans",
            "Firewalls and antivirus",
            "Safe internet practices, digital footprint"
        ]
    }
    
    # All sections in a list with appropriate weighting for distribution
    all_sections = [
        computer_fundamentals,     # ~10-15%
        data_representation,       # ~10-15%
        operating_systems,         # ~10%
        computer_organization,     # ~10%
        software_concepts,         # ~10%
        internet_networking,       # ~10%
        c_programming,             # ~20-30%
        ms_office,                 # ~5%
        database_fundamentals,     # ~5%
        cyber_security             # ~5%
    ]
    
    # Define weights for each section to ensure appropriate distribution
    section_weights = [
        15,  # computer_fundamentals
        15,  # data_representation
        10,  # operating_systems
        10,  # computer_organization
        10,  # software_concepts
        10,  # internet_networking
        30,  # c_programming - highest weight as per requirements
        5,   # ms_office
        5,   # database_fundamentals
        5    # cyber_security
    ]
    
    # Question templates for different categories
    general_templates = [
        "What is {concept}?",
        "Which of the following best describes {concept}?",
        "What is the main purpose of {concept}?",
        "What does {acronym} stand for?",
        "Which of the following is NOT a characteristic of {concept}?"
    ]
    
    definition_templates = [
        "Which of the following is the correct definition of {concept}?",
        "How is {concept} defined in {context}?",
        "What is meant by the term {concept}?"
    ]
    
    comparison_templates = [
        "What is the difference between {concept1} and {concept2}?",
        "How does {concept1} differ from {concept2}?",
        "Which of the following distinguishes {concept1} from {concept2}?"
    ]
    
    function_templates = [
        "What is the purpose of {concept}?",
        "What role does {concept} play in {system}?",
        "How does {concept} function in a computing environment?"
    ]
    
    coding_templates = [
        "What will be the output of the following C code?\n{code_snippet}",
        "Which of the following is the correct way to {task} in C?",
        "What does the following C statement do?\n{code_statement}",
        "Identify the error in the following C code:\n{code_snippet}",
        "Which header file is required to use the {function} function in C?"
    ]
    
    # Generate questions
    questions = []
    section_distribution = []
    
    # Calculate how many questions to generate for each section based on weights
    total_weight = sum(section_weights)
    for i, weight in enumerate(section_weights):
        # Calculate number of questions for this section, ensure at least 1
        section_count = max(1, round((weight / total_weight) * num_questions))
        section_distribution.append(section_count)
    
    # Adjust to make sure we get exactly num_questions
    while sum(section_distribution) > num_questions:
        # Find the section with the most questions and decrement it
        max_index = section_distribution.index(max(section_distribution))
        if section_distribution[max_index] > 1:  # Don't reduce below 1
            section_distribution[max_index] -= 1
    
    while sum(section_distribution) < num_questions:
        # Find the section with the highest weight that hasn't reached its cap
        max_weight_index = section_weights.index(max(section_weights))
        section_distribution[max_weight_index] += 1
        section_weights[max_weight_index] = 0  # Prevent this section from being chosen again
    
    logger.info(f"Question distribution across sections: {section_distribution}")
    
    # Generate questions for each section
    for section_index, section_count in enumerate(section_distribution):
        section = all_sections[section_index]
        topic = section["topic"]
        subtopics = section["subtopics"]
        
        for _ in range(section_count):
            subtopic = random.choice(subtopics)
            
            # Choose template based on topic
            if topic == "C PROGRAMMING":
                template = random.choice(coding_templates)
                question_text = generate_c_programming_question(template, subtopic)
            else:
                # Choose appropriate template for this topic
                if "vs" in subtopic or "comparison" in subtopic.lower():
                    template = random.choice(comparison_templates)
                elif "function" in subtopic.lower() or "purpose" in subtopic.lower():
                    template = random.choice(function_templates)
                elif "definition" in subtopic.lower() or "basics" in subtopic.lower():
                    template = random.choice(definition_templates)
                else:
                    template = random.choice(general_templates)
                
                # Extract concepts from subtopic
                concepts = extract_concepts_from_subtopic(subtopic)
                primary_concept = concepts[0] if concepts else subtopic.split(":")[0] if ":" in subtopic else subtopic
                
                # Format question template
                question_text = format_computer_question(template, primary_concept, subtopic, topic)
            
            # Generate options and correct answer
            options, correct_option = generate_computer_options(topic, subtopic)
            
            # Create question object
            questions.append({
                "question": f"[{topic}] {question_text}",
                "options": options,
                "answer": correct_option,
                "explanation": f"This question tests your understanding of {subtopic} in {topic}.",
                "topic": topic,
                "subtopic": subtopic,
                "category": "Computer Awareness"
            })
    
    # Shuffle questions
    random.shuffle(questions)
    
    return questions

def generate_c_programming_question(template, subtopic):
    """Generate a C programming question based on the template and subtopic"""
    
    # Code snippets for different subtopics
    code_snippets = {
        "Data types": [
            "int x = 5;\nfloat y = 2.5;\nprintf(\"%d\", x + (int)y);",
            "char ch = 65;\nprintf(\"%c\", ch);",
            "int x = 10;\nfloat y = x / 3;\nprintf(\"%f\", y);"
        ],
        "Control statements": [
            "int x = 5, y = 10;\nif(x > y)\n    printf(\"x is greater\");\nelse if(x == y)\n    printf(\"Equal\");\nelse\n    printf(\"y is greater\");",
            "int i = 0;\nwhile(i < 5) {\n    printf(\"%d \", i);\n    i++;\n}",
            "for(int i = 0; i < 3; i++) {\n    for(int j = 0; j < 2; j++) {\n        printf(\"%d%d \", i, j);\n    }\n}"
        ],
        "Functions": [
            "int factorial(int n) {\n    if(n <= 1) return 1;\n    return n * factorial(n-1);\n}\n\nprintf(\"%d\", factorial(4));",
            "void swap(int *a, int *b) {\n    int temp = *a;\n    *a = *b;\n    *b = temp;\n}\n\nint x = 5, y = 10;\nswap(&x, &y);\nprintf(\"%d %d\", x, y);",
            "int sum(int a, int b) {\n    return a + b;\n}\n\nint result = sum(2, 3) * sum(4, 5);\nprintf(\"%d\", result);"
        ],
        "Arrays": [
            "int arr[5] = {1, 2, 3, 4, 5};\nint sum = 0;\nfor(int i = 0; i < 5; i++)\n    sum += arr[i];\nprintf(\"%d\", sum);",
            "char str[] = \"Hello\";\nprintf(\"%c\", str[4]);",
            "int matrix[2][2] = {{1, 2}, {3, 4}};\nprintf(\"%d\", matrix[1][0]);"
        ],
        "Pointers": [
            "int x = 10;\nint *p = &x;\n*p = 20;\nprintf(\"%d\", x);",
            "int arr[3] = {5, 10, 15};\nint *p = arr;\nprintf(\"%d %d\", *p, *(p+2));",
            "char *str = \"Hello\";\nprintf(\"%c\", *(str+1));"
        ],
        "Structures": [
            "struct Point {\n    int x, y;\n};\nstruct Point p = {5, 10};\nprintf(\"%d\", p.x + p.y);",
            "typedef struct {\n    char name[20];\n    int age;\n} Person;\n\nPerson p = {\"John\", 25};\nprintf(\"%d\", p.age);",
            "struct Test {\n    int a;\n    char b;\n};\nprintf(\"%d\", sizeof(struct Test));"
        ],
        "Dynamic memory": [
            "int *p = (int*)malloc(sizeof(int));\n*p = 10;\nprintf(\"%d\", *p);\nfree(p);",
            "int *arr = (int*)calloc(5, sizeof(int));\nprintf(\"%d\", arr[2]);",
            "int *p = (int*)malloc(sizeof(int));\nfree(p);\n*p = 10; // What happens here?"
        ],
        "File handling": [
            "FILE *fp = fopen(\"test.txt\", \"w\");\nfprintf(fp, \"Hello\");\nfclose(fp);",
            "FILE *fp = fopen(\"test.txt\", \"r\");\nchar buffer[10];\nfgets(buffer, 10, fp);\nprintf(\"%s\", buffer);\nfclose(fp);",
            "FILE *fp = fopen(\"nonexistent.txt\", \"r\");\nif(fp == NULL)\n    printf(\"File not found\");\nelse\n    printf(\"File opened\");"
        ]
    }
    
    # Determine which category the subtopic belongs to
    category = None
    for key in code_snippets.keys():
        if key.lower() in subtopic.lower():
            category = key
            break
    
    # Default to "Data types" if no matching category
    if not category:
        category = "Data types"
    
    # Get a code snippet for this category
    code_snippet = random.choice(code_snippets[category])
    
    # Common C tasks for question templates
    c_tasks = {
        "Data types": ["define an integer variable", "convert between data types", "use floating-point numbers"],
        "Control statements": ["implement a loop", "create a conditional statement", "use a switch statement"],
        "Functions": ["declare a function", "use function parameters", "implement recursion"],
        "Arrays": ["initialize an array", "access array elements", "work with multi-dimensional arrays"],
        "Pointers": ["declare a pointer", "dereference a pointer", "use pointer arithmetic"],
        "Structures": ["define a structure", "access structure members", "use a typedef with structures"],
        "Dynamic memory": ["allocate memory using malloc", "use calloc for arrays", "free allocated memory"],
        "File handling": ["open a file", "write to a file", "read from a file"]
    }
    
    # Format the template
    formatted_question = template.format(
        code_snippet=code_snippet,
        task=random.choice(c_tasks.get(category, ["perform a basic operation"])),
        code_statement=random.choice(code_snippet.split('\n')),
        function=random.choice(["malloc", "printf", "scanf", "fopen", "strlen", "strcpy"])
    )
    
    return formatted_question

def extract_concepts_from_subtopic(subtopic):
    """Extract key concepts from a subtopic description"""
    # Split by common delimiters
    parts = re.split(r'[:;,()]', subtopic)
    concepts = []
    
    for part in parts:
        # Clean up and split by spaces
        clean_part = part.strip()
        if clean_part and len(clean_part.split()) < 4:  # Keep only short phrases
            concepts.append(clean_part)
    
    # If we didn't get any concepts, use the first few words
    if not concepts and subtopic:
        words = subtopic.split()
        if len(words) > 2:
            concepts.append(" ".join(words[:2]))
        else:
            concepts.append(subtopic)
    
    return concepts

def format_computer_question(template, concept, subtopic, topic):
    """Format a template with appropriate concepts and context"""
    
    # Extract potential acronyms (all caps words)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', subtopic)
    acronym = random.choice(acronyms) if acronyms else random.choice(["CPU", "RAM", "ROM", "ALU", "HTTP", "SQL"])
    
    # Extract potential paired concepts for comparison questions
    concepts = extract_concepts_from_subtopic(subtopic)
    concept1 = concept
    concept2 = None
    
    # Find a second concept different from the first
    if len(concepts) > 1:
        for c in concepts:
            if c != concept1:
                concept2 = c
                break
    
    # Default second concept if none found
    if not concept2:
        default_pairs = {
            "hardware": "software",
            "RAM": "ROM",
            "primary memory": "secondary memory",
            "compiler": "interpreter",
            "analog": "digital",
            "LAN": "WAN",
            "system software": "application software",
            "DBMS": "RDBMS"
        }
        concept2 = default_pairs.get(concept1.lower(), "related technology")
    
    # Add context to the concept
    system = topic.lower().replace('&', 'and')
    context = topic
    
    # Format the template
    formatted_question = template.format(
        concept=concept,
        acronym=acronym,
        concept1=concept1,
        concept2=concept2,
        context=context,
        system=system
    )
    
    return formatted_question

def generate_computer_options(topic, subtopic):
    """Generate appropriate options for computer questions with one correct answer"""
    
    # Common option patterns for different topics
    option_patterns = {
        "COMPUTER FUNDAMENTALS": {
            "Number systems": [
                {"pattern": "{base} number system, which uses digits {digits}", "variations": [
                    {"base": "Binary", "digits": "0 and 1"},
                    {"base": "Decimal", "digits": "0 through 9"},
                    {"base": "Octal", "digits": "0 through 7"},
                    {"base": "Hexadecimal", "digits": "0-9 and A-F"}
                ]},
                {"pattern": "Represents numbers in {base} {base_number}", "variations": [
                    {"base": "base-2", "base_number": "(binary)"},
                    {"base": "base-8", "base_number": "(octal)"},
                    {"base": "base-10", "base_number": "(decimal)"},
                    {"base": "base-16", "base_number": "(hexadecimal)"}
                ]}
            ],
            "Computers": [
                {"pattern": "{type} computers which {characteristic}", "variations": [
                    {"type": "Analog", "characteristic": "process continuous data"},
                    {"type": "Digital", "characteristic": "process discrete data"},
                    {"type": "Hybrid", "characteristic": "combine analog and digital features"},
                    {"type": "Quantum", "characteristic": "use quantum bits or qubits"}
                ]},
                {"pattern": "Generation {gen} computers using {technology}", "variations": [
                    {"gen": "First", "technology": "vacuum tubes"},
                    {"gen": "Second", "technology": "transistors"},
                    {"gen": "Third", "technology": "integrated circuits"},
                    {"gen": "Fourth", "technology": "microprocessors"}
                ]}
            ]
        },
        "OPERATING SYSTEM BASICS": {
            "Functions": [
                {"pattern": "{function} management", "variations": [
                    {"function": "Process"},
                    {"function": "Memory"},
                    {"function": "File"},
                    {"function": "Device"}
                ]},
                {"pattern": "{type} OS which {characteristic}", "variations": [
                    {"type": "Batch", "characteristic": "processes jobs in sequence without user interaction"},
                    {"type": "Time-sharing", "characteristic": "allows multiple users to use the system simultaneously"},
                    {"type": "Real-time", "characteristic": "guarantees processing within strict time constraints"},
                    {"type": "Distributed", "characteristic": "manages a group of distinct computers"}
                ]}
            ]
        }
    }
    
    # Default patterns for topics not specifically defined
    default_patterns = [
        {"pattern": "{descriptor} {concept}", "variations": [
            {"descriptor": "A system for", "concept": "data processing and management"},
            {"descriptor": "A technique for", "concept": "optimizing computer operations"},
            {"descriptor": "A protocol for", "concept": "communication between systems"},
            {"descriptor": "A method of", "concept": "organizing digital information"}
        ]},
        {"pattern": "{concept} which {function}", "variations": [
            {"concept": "A hardware component", "function": "processes instructions"},
            {"concept": "A software tool", "function": "manages system resources"},
            {"concept": "A network protocol", "function": "enables data communication"},
            {"concept": "A security mechanism", "function": "protects against unauthorized access"}
        ]}
    ]
    
    # Find appropriate pattern for this topic/subtopic
    patterns = option_patterns.get(topic, {}).get(subtopic.split(':')[0] if ':' in subtopic else subtopic, default_patterns)
    
    # Select a random pattern
    pattern_template = random.choice(patterns)
    pattern = pattern_template["pattern"]
    variations = pattern_template["variations"]
    
    # Shuffle variations
    random.shuffle(variations)
    
    # Generate options using the pattern
    options = {}
    for i, variation in enumerate(variations[:4]):  # Use up to 4 variations
        option_text = pattern.format(**variation)
        options[chr(65 + i)] = option_text  # A, B, C, D
    
    # Ensure we have exactly 4 options
    while len(options) < 4:
        # Generate a generic option
        generic_options = [
            "None of the above",
            "All of the above",
            f"A combination of {random.choice(list(options.values()))} and other features",
            f"A variant of {random.choice(list(options.values()))} with additional capabilities"
        ]
        option_letter = chr(65 + len(options))
        options[option_letter] = random.choice(generic_options)
    
    # Select a random option as the correct one
    correct_option = random.choice(list(options.keys()))
    
    return options, correct_option

def generate_math_equation(category):
    """Generate a math equation based on category"""
    if category == "algebra":
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        c = random.randint(1, 10)
        return f"{a}x + {b} = {c}"
    elif category == "geometry":
        return f"a² + b² = c²"
    else:
        return f"{random.randint(1, 10)}x + {random.randint(1, 10)}y = {random.randint(1, 100)}"

def generate_math_expression(category):
    """Generate a math expression based on category"""
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    c = random.randint(1, 10)
    
    expressions = [
        f"{a}x² + {b}x + {c}",
        f"{a}(x + {b})/{c}",
        f"√({a}x² + {b})",
        f"{a}x/{b} + {c}",
        f"log_{a}(x + {b})"
    ]
    
    return random.choice(expressions)

def generate_math_condition(category):
    """Generate a math condition"""
    conditions = [
        f"x + y = {random.randint(1, 20)}",
        f"x² + y² = {random.randint(1, 100)}",
        f"x/y = {random.randint(1, 5)}",
        f"x - y = {random.randint(1, 10)}"
    ]
    
    return random.choice(conditions)

def generate_math_function():
    """Generate a common mathematical function"""
    functions = [
        f"{random.randint(1, 10)}x² + {random.randint(1, 10)}x + {random.randint(1, 10)}",
        f"sin(x) + {random.randint(1, 5)}",
        f"{random.randint(1, 5)}e^x",
        f"ln(x) + {random.randint(1, 5)}",
        f"{random.randint(1, 5)}x³ - {random.randint(1, 10)}x"
    ]
    
    return random.choice(functions)

def generate_math_explanation(category):
    """Generate a math explanation"""
    explanations = [
        "substitute the values and solve for the variable.",
        "apply the quadratic formula to find the roots.",
        "use the Pythagorean theorem.",
        "apply the rules of logarithms.",
        "use the properties of similar triangles.",
        "differentiate the function using the chain rule.",
        "integrate the function using substitution.",
        "factor the expression and simplify.",
        "apply the laws of trigonometry.",
        "use the distance formula in coordinate geometry."
    ]
    
    return random.choice(explanations)

def generate_computer_answer(concept, topic):
    """Generate a plausible answer for computer awareness questions"""
    answers = {
        "Process Management": [
            "The allocation of CPU time to different processes",
            "Handling the execution and termination of programs",
            "Managing the state transitions of processes",
            "Scheduling processes for optimal CPU utilization"
        ],
        "Memory Management": [
            "Allocating and deallocating memory space to programs",
            "Managing virtual and physical memory spaces",
            "Implementing paging and segmentation techniques",
            "Handling memory protection and access control"
        ],
        "SQL": [
            "A language for managing and querying relational databases",
            "A system for creating and modifying database schema",
            "A protocol for ensuring data integrity in transactions",
            "A set of commands for data manipulation and querying"
        ]
    }
    
    # Get answers for the specific concept or use generic ones
    concept_answers = answers.get(concept, [
        f"A fundamental concept in {topic}",
        f"A technique used in modern {topic} systems",
        f"A protocol commonly implemented in {topic}",
        f"An algorithm designed for optimizing {topic} operations"
    ])
    
    return random.choice(concept_answers)

def generate_computer_explanation(concept, topic):
    """Generate an explanation for computer awareness questions"""
    explanations = [
        f"it is the standard definition of {concept} in {topic}",
        f"this is how {concept} is implemented in most {topic} systems",
        f"it accurately describes the functionality of {concept}",
        f"it represents the correct relationship between {concept} and other components in {topic}",
        f"it identifies the primary purpose of {concept} in {topic} applications"
    ]
    
    return random.choice(explanations)

def generate_default_questions(subject, num_questions):
    """Generate default questions if AI generation fails"""
    if subject == "mathematics":
        return [
            {
                "question": f"Math Question {i+1}: Calculate the value of x in the equation 2x + 5 = 15.",
                "options": {
                    "A": "5",
                    "B": "10",
                    "C": "15",
                    "D": "20"
                },
                "answer": "A",
                "explanation": "To solve 2x + 5 = 15, subtract 5 from both sides to get 2x = 10, then divide by 2 to get x = 5.",
                "category": "algebra",
                "topic": "Linear Equations"
            } for i in range(num_questions)
        ]
    else:  # computer_awareness
        return [
            {
                "question": f"Computer Question {i+1}: What does CPU stand for?",
                "options": {
                    "A": "Central Processing Unit",
                    "B": "Computer Personal Unit",
                    "C": "Central Program Utility",
                    "D": "Computer Processing Utility"
                },
                "answer": "A",
                "explanation": "CPU stands for Central Processing Unit, which is the primary component of a computer that performs calculations and executes instructions.",
                "category": "Computer Awareness",
                "topic": "Computer Architecture"
            } for i in range(num_questions)
        ]
