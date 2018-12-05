/**
 * Created by eamonnmaguire on 16/03/2016.
 */

HEPDATA = {};

HEPDATA.interval = undefined;

HEPDATA.default_error_label = "";
HEPDATA.show_review = true;
HEPDATA.default_errors_to_show = 3;
HEPDATA.default_row_limit = 50;
HEPDATA.current_record_id = undefined;
HEPDATA.current_table_id = undefined;
HEPDATA.current_table_name = undefined;
HEPDATA.current_table_version = undefined;
HEPDATA.clipboard = undefined;
HEPDATA.selected = undefined;
HEPDATA.site_url = "https://www.hepdata.net";

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
  "madanalysis": {"icon": "area-chart", "description": "MadAnalysis5 Analysis"},
  "xfitter": {"icon": "area-chart", "description": "xFitter Analysis"},
  "applgrid": {"icon": "area-chart", "description": "APPLgrid Analysis"},
  "ufo": {"icon": "rocket", "description": "Universal Feynrules Output (UFO)"},
  "html": {"icon": "code", "description": "External Link"},
  "oldhepdata": {"icon": "file-text-o", "description": "Legacy HEPData Format"},
  "root": {"icon": "line-chart", "description": "ROOT File"}
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
      console.log(data);
      if (data.success) {
        $("#deleteDialogLabel").text("Submission Deleted");
        $("#progress").addClass("hidden");
        $("#delete-success").removeClass("hidden");

        var count = 5;
        setInterval(function () {
          count -= 1;
          $("#timer").text(count);
          if (count == 0) {
            $("#deleteWidget").modal('hide');
          }
        }, 1000);

        setTimeout(function () {
          window.location = redirect_url;
        }, 5500);


      } else {
        alert("Error! " + data.message)
      }
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

  file_type_lower = file_type.toLowerCase();
  var mapping = HEPDATA.file_type_to_details[file_type_lower];
  if (mapping) {
    return HEPDATA.file_type_to_details[file_type_lower][property];
  }

  if (property === "icon") return 'file-text-o';
  if (property === "description") return file_type + ' File';

};

HEPDATA.render_associated_files = function (associated_files, placement) {
  $(placement).html('');
  $("#figures").html('');

  for (var file_index in associated_files) {
    var file = associated_files[file_index];
    var html = '';
    $(placement).append('button').attr('class', 'btn btn-primary pull-right')
      .attr('id', 'show_resources').text('Resources');

    if ('preview_location' in file) {
      $("#figures")
        .append('<a class="support-file" data-file-id="' + file.id + '">' +
          '<img src="' + file['preview_location'] + '"/>' +
          '</a>');
    }
    $(placement).append(html);
  }
};
