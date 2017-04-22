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

mapping = {
    "abstract": {
        "type": "string",
        # "analyzer": "english"
    },
    "authors": {
        "type": "nested",
        "properties": {
            "affiliation": {
                "type": "string"
            },
            "first_name": {
                "type": "string"
            },
            "full_name": {
                "type": "string",
                "index": "not_analyzed"
            },
            "last_name": {
                "type": "string"
            }
        }
    },

    "summary_authors": {
        "type": "nested",
        "properties": {
            "affiliation": {
                "type": "string"
            },
            "first_name": {
                "type": "string"
            },
            "full_name": {
                "type": "string",
                "index": "not_analyzed"
            },
            "last_name": {
                "type": "string"
            }
        }
    },

    "collaborations": {
        "type": "string",
        "fields": {
            "raw": {
                "type": "string",
                "index": "not_analyzed"
            }
        }
    },

    "subject_area": {
        "type": "string",
        "fields": {
            "raw": {
                "type": "string",
                "index": "not_analyzed"
            }
        }
    },

    "type": {
        "type": "string"
    },

    "analyses": {
        "type": "nested",
        "properties": {
            "type": {
                "type": "string"
            },
            "analysis": {
                "type": "string"
            }
        }
    },

    "dissertation": {
        "type": "nested",
        "properties": {
            "type": {
                "type": "string"
            },
            "institution": {
                "type": "string"
            },
            "defense_data": {
                "type": "string"
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
        "type": "string",
        "index": "not_analyzed"
    },
    "hepdata_doi": {
        "type": "string"
    },
    "data_keywords": {
        "properties": {
            "cmenergies": {
                "type": "string",
                "fields": {
                    "raw": {
                        "type": "string",
                        "index": "analyzed"
                    }
                }
            },
            "observables": {
                "type": "string",
                "fields": {
                    "raw": {
                        "type": "string",
                        "index": "not_analyzed"
                    }
                }
            },
            "phrases": {
                "type": "string",
                "fields": {
                    "raw": {
                        "type": "string",
                        "index": "not_analyzed"
                    }
                }
            },
            "reactions": {
                "type": "string",
                "fields": {
                    "raw": {
                        "type": "string",
                        "index": "not_analyzed"
                    }
                }
            }
        }
    },
    "inspire_id": {
        "type": "string"
    },
    "keywords": {
        "properties": {
            "name": {
                "type": "string"
            },
            "value": {
                "type": "string"
            },
            "synonyms": {
                "type": "string"
            }
        }
    },
    "recid": {
        "type": "integer"
    },
    "title": {
        "type": "string",
        "fields": {
            "raw": {
                "type": "string",
                "index": "analyzed"
            }
        }
    }
}
