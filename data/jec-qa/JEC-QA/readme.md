# JEC-QA

Before using JEC-QA, please carefully read and strictly follow the rules [here](http://jecqa.thunlp.org/readme).

You can also view our [homepage](http://jecqa.thunlp.org/) for more information.



## Data File

The four files ``0_train.json,0_test.json,1_train.json,1_test.json`` denotes the questions of JEC-QA. Here files starts with 0 contain KD-questions while others contain CA-questions. Every line of the file contains a data in json format, and there are six different fields:

* "statement". The description of the questions.
* "option_list". The description of four options.
* "answer": The answer to the questions. (Only in training data)
* "id":  A unique id for every question.
* "subject": The subject involved by the questions. Only part of the questions have this field.
* "type": Denote whether the question is a KD-question or CA-question.



## Reference

The reference book is stored in the directory ``reference_book``, every file is a single json file which contains a section of the book.



## Submission

To evaluate your methods on test dataset, you can submit it to [CodaLab](https://competitions.codalab.org/competitions/22173). We have provided an example in the directory ``submit_sample``. You can read it for more information.