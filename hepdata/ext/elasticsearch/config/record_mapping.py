#
# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
#
from hepdata.config import CFG_PUB_TYPE, CFG_DATA_TYPE

mapping = {
    "doc_type": {
        "type": "keyword"
    },
    "abstract": {
        "type": "text",
        # "analyzer": "english"
    },
    "authors": {
        "type": "nested",
        "properties": {
            "affiliation": {
                "type": "text"
            },
            "full_name": {
                "type": "text",
                "fields": {
                    "raw": {
                        "type": "keyword",
                        "index": "true"
                    }
                }
            }
        }
    },

    "summary_authors": {
        "type": "nested",
        "properties": {
            "affiliation": {
                "type": "text"
            },
            "full_name": {
                "type": "text",
                "fields": {
                    "raw": {
                        "type": "keyword",
                        "index": "true"
                    }
                }
            }
        }
    },

    "collaborations": {
        "type": "text",
        "fields": {
            "raw": {
                "type": "keyword",
                "index": "true"
            }
        }
    },

    "subject_area": {
        "type": "text",
        "fields": {
            "raw": {
                "type": "keyword",
                "index": "true"
            }
        }
    },

    "type": {
        "type": "text"
    },

    "analyses": {
        "type": "nested",
        "properties": {
            "type": {
                "type": "text"
            },
            "analysis": {
                "type": "text"
            }
        }
    },

    "dissertation": {
        "type": "nested",
        "properties": {
            "type": {
                "type": "text"
            },
            "institution": {
                "type": "text"
            },
            "defense_date": {
                "type": "text"
            }
        }
    },
    "creation_date": {
        "type": "date",
        "format": "dateOptionalTime"
    },
    "publication_year": {
        "type": "date",
        "format": "dateOptionalTime"
    },
    "last_updated": {
        "type": "date",
        "format": "yyyy-MM-dd'T'HH:mm:ss"
    },
    "doi": {
        "type": "keyword",
        "index": "true"
    },
    "hepdata_doi": {
        "type": "text"
    },
    "data_keywords": {
        "properties": {
            "cmenergies": {
                "type": "float_range",
            },
            "observables": {
                "type": "text",
                "fields": {
                    "raw": {
                        "type": "keyword",
                        "index": "true"
                    }
                }
            },
            "phrases": {
                "type": "text",
                "fields": {
                    "raw": {
                        "type": "keyword",
                        "index": "true"
                    }
                }
            },
            "reactions": {
                "type": "text",
                "fields": {
                    "raw": {
                        "type": "keyword",
                        "index": "true"
                    }
                }
            }
        }
    },
    "inspire_id": {
        "type": "text"
    },
    "keywords": {
        "properties": {
            "name": {
                "type": "text"
            },
            "value": {
                "type": "text"
            },
            "synonyms": {
                "type": "text"
            }
        }
    },
    "recid": {
        "type": "integer"
    },
    "title": {
        "type": "text",
        "fields": {
            "raw": {
                "type": "keyword",
                "index": "true"
            }
        }
    },
    "parent_child_join": {
        "type": "join",
        "relations": {
            "parent_publication": "child_datatable"
        }
    }
}
