import json
import os


def main():
    files_dir = 'quiz-questions'
    questions_and_answers = dict()
    for dirpath, dirnames, filenames in os.walk(files_dir):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            with open(filepath, 'r', encoding='koi8-r') as f:
                quiz_blocks = f.read().split('\n\n\n')
                for quiz_block in quiz_blocks:
                    points = quiz_block.split('\n\n')
                    for point in points:
                        if point.startswith('Вопрос '):
                            question = point
                        if point.startswith('Ответ:'):
                            answer = point[7:]
                            questions_and_answers[question] = answer
                            break
    with open('question-answer.json', 'w', encoding='utf-8') as json_file:
        json.dump(questions_and_answers, json_file, ensure_ascii=False)


if __name__ == '__main__':
    main()
