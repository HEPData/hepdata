/**
 * Created by eamonnmaguire on 16/03/2016.
 */
import $ from 'jquery'
import ClipboardJS from 'clipboard'
import toastr from 'toastr'

var HEPDATA = {};

HEPDATA.interval = undefined;

HEPDATA.default_error_label = "";
HEPDATA.show_review = true;
HEPDATA.default_errors_to_show = 3;
HEPDATA.default_row_limit = 50;
HEPDATA.current_record_id = undefined;
HEPDATA.current_table_id = undefined;
HEPDATA.current_table_name = undefined;
HEPDATA.current_table_version = undefined;
HEPDATA.current_observer_key = undefined;
HEPDATA.clipboard = undefined;
// Stores a list of CSS selectors to track added Clipboards
HEPDATA.clipboard_list = [];
HEPDATA.selected = {};
HEPDATA.site_url = "https://www.hepdata.net";
HEPDATA.OBSERVER_KEY_LENGTH = 8;

HEPDATA.current_filters = {
  "text": "",
  "progress": "",
  "role": ""
};

HEPDATA.review_classes = {
  "attention": {
    "icon": "fa-exclamation-triangle",
    "text": "attention required"
  },
  "todo": {"icon": "fa-exclamation-triangle", "text": "to be reviewed"},
  "passed": {"icon": "fa-check-circle", "text": "passed review"}
};


HEPDATA.file_type_to_details = {
  "image": {"icon": "image", "description": "Image File"},
  "github": {"icon": "github", "description": "GitHub Repository"},
  "gitlab": {"icon": "gitlab", "description": "GitLab Repository"},
  "bitbucket": {"icon": "bitbucket", "description": "Bitbucket Repository"},
  "fastnlo": {"icon": "area-chart", "description": "fastNLO Analysis"},
  "rivet": {"icon": "area-chart", "description": "Rivet Analysis"},
  "madanalysis": {"icon": "area-chart", "description": "MadAnalysis 5 Analysis"},
  "smodels": {"icon": "area-chart", "description": "SModelS Analysis"},
  "checkmate": {"icon": "area-chart", "description": "CheckMATE Analysis"},
  "hackanalysis": {"icon": "area-chart", "description": "HackAnalysis Analysis"},
  "combine": {"icon": "area-chart", "description": "Combine Analysis"},
  "gambit": {"icon": "area-chart", "description": "GAMBIT analysis"},
  "xfitter": {"icon": "area-chart", "description": "xFitter Analysis"},
  "applgrid": {"icon": "area-chart", "description": "APPLgrid Analysis"},
  "ufo": {"icon": "rocket", "description": "Universal Feynrules Output (UFO)"},
  "html": {"icon": "code", "description": "External Link"},
  "oldhepdata": {"icon": "file-text-o", "description": "Legacy HEPData Format"},
  "root": {"icon": "line-chart", "description": "ROOT File"},
  "zenodo": {"icon": "code", "description": "Zenodo Record"}
};

HEPDATA.stats = {
  min_x: Number.MAX_VALUE,
  max_x: Number.MIN_VALUE,
  min_y: Number.MAX_VALUE,
  max_y: Number.MIN_VALUE,
  min_value: Number.MAX_VALUE,
  max_value: Number.MIN_VALUE
};

HEPDATA.reset_stats = function () {
  HEPDATA.stats.min_y = Number.MAX_VALUE;
  HEPDATA.stats.max_y = Number.MIN_VALUE;
  HEPDATA.stats.min_x = Number.MAX_VALUE;
  HEPDATA.stats.max_x = Number.MIN_VALUE;
  HEPDATA.stats.min_value = Number.MAX_VALUE;
  HEPDATA.stats.max_value = Number.MIN_VALUE;
};

HEPDATA.delete_submission = function (record_id, redirect_url) {
  $.ajax({
    dataType: "json",
    url: '/dashboard/delete/' + window.recid,
    success: function (data) {
        $("#progress").addClass("hidden");
        if (data.success) {
          $("#delete-success").removeClass("hidden");
        } else {
          $("#delete-failure").removeClass("hidden");
          $("#deleteDialogMessage").text(data.message);
        }

        var count = 5;
        setInterval(function () {
          count -= 1;
          $(".timer").text(count);
          if (count == 0) {
            $("#deleteWidget").modal('hide');
          }
        }, 1000);

        setTimeout(function () {
          window.location = redirect_url;
        }, 5500);

    }
  })
};

/**
 * Reindex an individual record, or all records if the record id is -1
 * @param record_id if -1 reindexes all records. Otherwise just that specified.
 */
HEPDATA.reindex = function () {

  $("#reindex-button").addClass("disabled");
  var count = 5;
  setInterval(function () {
    count -= 1;
    $("#reindex-timer").text(count);
    if (count == 0) {
      $("#reindexWidget").modal('hide');
    }
  }, 1000);

  $.ajax({
    method: 'POST',
    url: '/dashboard/manage/reindex/',
    success: function (data) {
      if (!data.success) {
        alert('Failed to reindex database.')
      } else {
        $("#reindex-button").removeClass("disabled");
      }
    }
  })
};

HEPDATA.update_coordinator = function (recid, coordinator) {
  $.ajax({
    method: 'POST',
    url: '/permissions/manage/coordinator/',
    data: {'recid': recid, 'coordinator': coordinator},
    success: function (data) {
      if (!data.success) {
        alert('Failed to change the coordinator for this record.')
      }
    }
  })
};


/* Filters out content of a list defined by the listId
 given the content of filters defined in HEPDATA.current_filters.* .*/
HEPDATA.filter_content = function (filterInputId, listId) {
  if (filterInputId != "") {
    HEPDATA.current_filters.text = $(filterInputId).val().toLowerCase();
  }
  $(listId + '>li').each(function () {
    var text = $(this).text().toLowerCase().trim();
    var ok_to_show = true;

    for (var filter in HEPDATA.current_filters) {
      if (HEPDATA.current_filters[filter] != "") {
        if (text.indexOf(HEPDATA.current_filters[filter].toLowerCase()) == -1) {
          ok_to_show = false;
          break;
        }
      }
    }
    if (ok_to_show) {
      $(this).fadeIn(500);
    } else {
      $(this).fadeOut(500);
    }
  });
};

/**
 * Counts the number of decimal places for a value.
 * Check if value is given in scientific notation.
 * @param number
 * @returns {*|number}
 */

HEPDATA.count_decimals = function (number) {
  if (number.toString().indexOf('.') != -1) {
    var rightofpoint = number.toString().split(".")[1];
    if (rightofpoint.toLowerCase().indexOf('e') != -1)
      return rightofpoint.toLowerCase().split('e')[0].length || 2;
    else
      return rightofpoint.length || 2;
  }
  return 0;
}

HEPDATA.is_image = function (file_type) {
  var image_file_types = ["png", "jpeg", "jpg", "tiff", "gif"];
  return image_file_types.indexOf(file_type.toLowerCase()) != -1
};

/**
 * @param file_type e.g. github
 * @param property e.g. icon
 */
HEPDATA.map_file_type_to_property = function (file_type, property) {

  var file_type_lower = file_type.toLowerCase();
  var mapping = HEPDATA.file_type_to_details[file_type_lower];
  if (mapping) {
    return HEPDATA.file_type_to_details[file_type_lower][property];
  }

  if (property === "icon") return 'file-text-o';
  if (property === "description") return file_type + ' File';

};

HEPDATA.render_associated_files = function (associated_files, placement, observer_key) {
  $(placement).html('');
  $("#figures").html('');

  for (var file_index in associated_files) {
    var file = associated_files[file_index];
    var html = '';
    $(placement).append('button').attr('class', 'btn btn-primary pull-right')
      .attr('id', 'show_resources').text('Resources');

    if ('preview_location' in file) {
      var preview_location = file['preview_location'];
      var data_file_id = file.id;
      if (observer_key && observer_key.length === HEPDATA.OBSERVER_KEY_LENGTH) {
        preview_location += "&observer_key=" + observer_key;
        data_file_id += "?observer_key=" + observer_key;
      }
      $("#figures")
        .append('<a class="support-file" data-file-id="' + data_file_id + '">' +
          '<img src="' + preview_location + '"/>' +
          '</a>');
    }
    $(placement).append(html);
  }
};

HEPDATA.setup_default_clipboards = function () {
  /*
  Sets up the default clipboards for the base HEPData webpage, and triggers
  adding associated success/error event listeners.
  */
  if (HEPDATA.clipboard == undefined) {
    HEPDATA.clipboard = HEPDATA.setup_clipboard('.copy-btn');
    HEPDATA.observer_clipboard = HEPDATA.setup_clipboard('.observer-copy-btn');
    HEPDATA.cite_clipboard = HEPDATA.setup_clipboard('.cite-copy-btn');

    toastr.options.timeOut = 3000;
  }
};

HEPDATA.setup_clipboard = function(selector) {
  /*
    Sets up a ClipboardJS object from a CSS selector.

    @param {string} selector - A CSS selector used to select objects for clipboard
  */

  toastr.options.timeOut = 3000;

  // If we have already set this clipboard up, we return null
  if(HEPDATA.clipboard_list.includes(selector)) {
    return null;
  }
  else {
    // Push selector to the list to avoid adding duplicate events
    HEPDATA.clipboard_list.push(selector);
  }

  // Select all buttons in the document based on the selector
  let button_objects = document.querySelectorAll(selector);

  // Get the ClipboardJS object from the objects.
  let clipboard = new ClipboardJS(button_objects);

  // Add the clipboard's success and error toasts.
  clipboard.on('success', function (e) {
    toastr.success(e.text + ' copied to clipboard.')
  });

  clipboard.on('error', function (e) {
  if (navigator.userAgent.indexOf("Safari") > -1) {
    toastr.success('Press &#8984; + C to finalise copy');
  } else {
    toastr.error('There was a problem copying the link.');
  }
  })

  return clipboard;
}

HEPDATA.get_observer_key_data = function(recid, as_url) {
    /**
    * Requests the observer key data from a recid for URL display purposes.
    * Optionally can be returned as the record URL.
    *
    * @param {number} recid - The recid to get observer_key for.
    * @param {number} as_url - When set to "1", will request response as a full access URL
    * @return {Promise} - Returns the request promise to later retrieve the observer key
    */

    let request_url = '/record/coordinator/observer_key/' + recid;
    // Setting the request flag if required
    if (as_url === 1) request_url += '/1';

    return $.ajax({
      dataType: 'json',
      url: request_url,
      processData: false,
      cache: true
    }).then(function (data) {
      HEPDATA.current_observer_key = data['observer_exists'] ? data['observer_key'] : null;
      return HEPDATA.current_observer_key;
    });
};

window.HEPDATA = HEPDATA;
export default HEPDATA;
