import pyLDAvis.lda_model


def draw_intertopic_distance_map(dir_, model, model_type):
    """

    Args:
        dir_: a str
        model: a topic model (LDATopicModel or BERTopicModel)
        model_type: a str

    Returns:
        None
    """
    if model_type == 'bert_based':
        _draw_intertopic_distance_map_bert(model, dir_)
    elif model_type == 'lda':
        _draw_intertopic_distance_map_lda(model, dir_)


def _draw_intertopic_distance_map_lda(model, save_dir,
                                      title="topic_distance_map"):
    """

    Args:
        model: a LDATopicModel
        save_dir: a str
        title: a str

    Returns:
        None
    """
    sklearn_model = model.topic_model
    vectorized = model.vectorized
    vectorizer = model.vectorizer
    panel = pyLDAvis.lda_model.prepare(sklearn_model, vectorized, vectorizer,
                                       mds="tsne")
    print(f"[Saving] {save_dir}/{title}.html")
    pyLDAvis.save_html(panel, f"{save_dir}/{title}.html")


def _draw_intertopic_distance_map_bert(model, save_dir,
                                       title="topic_distance_map"):
    """

    Args:
        model: a BERTopicModel
        save_dir: a str
        title: a str

    Returns:
        None
    """
    fig = model.topic_model.visualize_topics()
    print(f"[Saving] {save_dir}/{title}.html")
    fig.write_html(f"{save_dir}/{title}.html")
