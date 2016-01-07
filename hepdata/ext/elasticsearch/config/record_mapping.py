#
# This file is part of HEPData.
# Copyright (C) 2015 CERN.
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
                "index": "analyzed"
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
                "index": "analyzed"
            }
        }
    },
    "creation_date": {
        "type": "date",
        "format": "dateOptionalTime"
    },
    "last_updated": {
        "type": "date",
        "format": "dateOptionalTime"
    },
    "doi": {
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
                        "index": "analyzed"
                    }
                }
            },
            "reactions": {
                "type": "string",
                "fields": {
                    "raw": {
                        "type": "string",
                        "index": "analyzed"
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
    "reviewers": {
        "properties": {
            "email": {
                "type": "string"
            },
            "first_name": {
                "type": "string"
            },
            "full_name": {
                "type": "string"
            },
            "last_name": {
                "type": "string"
            }
        }
    },
    "title": {
        "type": "string",
        "fields": {
            "raw": {
                "type": "string",
                "index": "analyzed"
            }
        }
    },
    "uploaders": {
        "properties": {
            "email": {
                "type": "string"
            },
            "first_name": {
                "type": "string"
            },
            "full_name": {
                "type": "string"
            },
            "last_name": {
                "type": "string"
            }
        }
    },
    "revision_messages": {
        "properties": {
            "version": {
                "type": "integer"
            },
            "message": {
                "type": "string"
            }
        }
    }
}
