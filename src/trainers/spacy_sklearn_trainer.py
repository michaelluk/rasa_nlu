import spacy
import os
import datetime
import json
import cloudpickle
from rasa_nlu.featurizers.spacy_featurizer import SpacyFeaturizer
from rasa_nlu.extractors.spacy_entity_extractor import SpacyEntityExtractor
from rasa_nlu.trainers import sklearn_trainer_utils
from rasa_nlu.trainers.trainer import Trainer
from training_utils import write_training_metadata
from rasa_nlu.utils.spacy import ensure_proper_language_model


class SpacySklearnTrainer(Trainer):
    SUPPORTED_LANGUAGES = {"en", "de"}

    def __init__(self, language_name, max_num_threads=1):
        super(self.__class__, self).__init__("spacy_sklearn", language_name, max_num_threads)
        self.nlp = spacy.load(self.language_name, parser=False, entity=False)
        self.featurizer = SpacyFeaturizer(self.nlp)
        ensure_proper_language_model(self.nlp)

    def train_entity_extractor(self, entity_examples):
        self.entity_extractor = SpacyEntityExtractor()
        self.entity_extractor = self.entity_extractor.train(self.nlp, entity_examples)

    def train_intent_classifier(self, intent_examples, test_split_size=0.1):
        self.intent_classifier = sklearn_trainer_utils.train_intent_classifier(intent_examples,
                                                                               self.featurizer,
                                                                               self.max_num_threads,
                                                                               test_split_size)

    def persist(self, path, persistor=None, create_unique_subfolder=True):
        entity_extractor_file, entity_extractor_config_file = None, None
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

        if create_unique_subfolder:
            dir_name = os.path.join(path, "model_" + timestamp)
            os.mkdir(dir_name)
        else:
            dir_name = path

        data_file = os.path.join(dir_name, "training_data.json")
        classifier_file, ner_dir = None, None
        if self.intent_classifier:
            classifier_file = os.path.join(dir_name, "intent_classifier.pkl")
        if self.entity_extractor:
            ner_dir = os.path.join(dir_name, 'ner')
            if not os.path.exists(ner_dir):
                os.mkdir(ner_dir)
            entity_extractor_config_file = os.path.join(ner_dir, "config.json")
            entity_extractor_file = os.path.join(ner_dir, "model")

        write_training_metadata(dir_name, timestamp, data_file, self.name, self.language_name,
                                classifier_file, ner_dir)

        with open(data_file, 'w') as f:
            f.write(self.training_data.as_json(indent=2))
        if self.intent_classifier:
            with open(classifier_file, 'wb') as f:
                cloudpickle.dump(self.intent_classifier, f)
        if self.entity_extractor:
            with open(entity_extractor_config_file, 'w') as f:
                json.dump(self.entity_extractor.ner.cfg, f)

            self.entity_extractor.ner.model.dump(entity_extractor_file)

        if persistor is not None:
            persistor.send_tar_to_s3(dir_name)
