HEPDATA = {};

HEPDATA.interval = undefined;

HEPDATA.default_error_label = "";
HEPDATA.show_review = true;
HEPDATA.default_errors_to_show = 3;
HEPDATA.current_record_id = undefined;
HEPDATA.current_table_id = undefined;
HEPDATA.current_table_version = undefined;

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


HEPDATA.switch_table = function (listId, table_requested) {
  // clear the active class
  $(listId + '>li').each(function () {
    $(this).removeClass("active")
  });
  // now set the active class on the table just selected
  $('#' + table_requested).addClass("active");


  HEPDATA.render_loader("#table_loader", [
      {x: 26, y: 30, color: "#955BA5"},
      {x: -60, y: 55, color: "#2C3E50"},
      {x: 37, y: -10, color: "#955BA5"},
      {x: -60, y: 10, color: "#955BA5"},
      {x: -27, y: -30, color: "#955BA5"},
      {x: 60, y: -55, color: "#2C3E50"}],
    {"width": 200, "height": 200}
  );

  $("#hepdata_table_loader").removeClass("hidden");
  $("#hepdata_table_content").addClass("hidden");

  HEPDATA.current_table_id = table_requested;

  if (HEPDATA.show_review) {
    HEPDATA.load_review_messages("#review_messages",
      HEPDATA.current_record_id,
      HEPDATA.current_table_id);
  }
  HEPDATA.table_renderer.display_table('/record/data/' + HEPDATA.current_record_id + '/' + table_requested + "/" + HEPDATA.current_table_version,
    '#data_table_region',
    '#data_visualization_region');

  $(".data_download_link").each(function () {
    var data_format = $(this).text().toLowerCase();
    var data_url = '/download/table/'
      + HEPDATA.current_table_id + '/'
      + data_format;
    $(this).attr('href', data_url);
  });
};

HEPDATA.set_review_status = function (status) {

  $.ajax({
      type: "POST",
      url: "/record/data/review/status/",
      dataType: "json",
      data: {
        "publication_recid": HEPDATA.current_record_id,
        "data_recid": HEPDATA.current_table_id,
        "status": status,
        "version": HEPDATA.current_table_version
      },
      cache: false,
      success: function (data) {
        var status = data.status;
        for (var review_status in HEPDATA.review_classes) {
          $("#reviewer-button").removeClass(review_status);
        }
        $("#reviewer-button").addClass(status);

        $("#" + status + "-option").removeClass("deactivate");
        $("#review-status span").each(function () {
          if (this.id.indexOf(status) == -1)
            $(this).addClass("deactivate");
        });

        for (var review_status in HEPDATA.review_classes) {
          $("#" + HEPDATA.current_table_id + "-status").removeClass(review_status);
        }
        $("#" + HEPDATA.current_table_id + "-status").addClass(status);
        $("#" + HEPDATA.current_table_id + "-status #icon").removeClass();
        $("#" + HEPDATA.current_table_id + "-status #icon").addClass("fa " + HEPDATA.review_classes[status].icon);
        $("#" + HEPDATA.current_table_id + "-status .text").text(HEPDATA.review_classes[status].text);
      }
    }
  );
};


HEPDATA.delete_submission = function (record_id, redirect_url) {
  $.ajax({
    dataType: "json",
    url: '/dashboard/delete/' + window.recid,
    success: function (data) {
      console.log(data);
      if (data.success) {
        $("#deleteDialogLabel").text("Submisson Deleted");
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
    url: '/dashboard/manage/coordinator/',
    data: {'recid': recid, 'coordinator': coordinator},
    success: function (data) {
      if (!data.success) {
        alert('Failed to change the coordinator for this record.')
      }
    }
  })
};

HEPDATA.load_all_review_messages = function (placement, record_id) {

  $.ajax({
    type: "GET",
    url: "/record/data/review/message/" + record_id,
    dataType: "json",
    cache: false,
    success: function (data) {
      $(placement).html('');
      var message_count = 0;
      for (var table in data) {
        d3.select(placement).append('p').attr('class', 'table-name').text(table);
        message_count += data[table].length;
        for (var message_idx in data[table]) {
          var message_data = data[table][message_idx];
          HEPDATA.render_review_message(placement, message_data);
        }

        $("#table-" + HEPDATA.current_table_id + "-messages").removeClass("hidden");
        $(".loading").addClass("hidden");
        $(".input_box").css("color", "#808080")
          .css("height", "30px");
        $("#conversation_message_count").html(message_count);
      }
      $("#conversation_message_count").html(message_count);
    }
  });
};

HEPDATA.render_review_message = function (placement, message) {
  var date_time = message.post_time.split(" ");
  var message_item = d3.select(placement).append('div').attr('class', 'message-item');
  var message_info = message_item.append('div').attr('class', 'message-info');
  message_info.append('p').attr('class', 'message-time').html(date_time[0] + '<br/>' + date_time[1]);
  var message_div = message_item.append('div').attr('class', 'message-content');
  message_div.append('p').attr('class', 'reviewer').text(message.user);
  message_div.append('p').text(message.message);
};

HEPDATA.load_review_messages = function (placement, record_id, table_id) {
  d3.select(placement).html('');
  $.ajax({
      type: "GET",
      url: "/record/data/review/message/" + record_id + "/" + table_id + "/" + HEPDATA.current_table_version,
      dataType: "json",
      cache: false,
      success: function (data) {

        if (data.length > 0) {

          for (var message_idx in data) {
            HEPDATA.render_review_message(placement, data[message_idx]);
          }
        } else {
          d3.select(placement).append('div').append('p').text('No messages yet...');
        }

      }
    }
  );
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

HEPDATA.is_image = function (file_path) {
  var image_file_types = ["png", "jpeg", "jpg", "tiff"];
  return image_file_types.indexOf(file_path.toLowerCase) != -1
};

HEPDATA.render_associated_files = function (associated_files, placement) {
  $(placement).html('');

  for (var file_index in associated_files) {

    var file = associated_files[file_index];

    console.log(file);

    var link = file['alt_location'];
    if (file.type == 'github') {
      html = '<a href="' + link + '" class="btn btn-md support-file-link" target="_blank">Code in ' + file.type + '</a>'
    } else if (HEPDATA.is_image(file.type.toLowerCase())) {
      html = '<button type="button" class="btn btn-md support-file" data-file-id="' + file.id + '">Associated Figure</button>';
    }
    else {
      html = '<button type="button" class="btn btn-md support-file" data-file-id="' + file.id + '">' + file.type + '</button>';
    }
    $(placement).append(html);

  }
};

HEPDATA.table_renderer = {
  display_table: function (url, table_placement, visualization_placement) {

    $.ajax({
      dataType: "json",
      url: url,
      processData: false,
      cache: true,
      success: function (table_data) {
        // display the table
        $(table_placement).html('');


        $("#table_name").html(table_data.name);
        $("#table_description").html(table_data.description.trim());

        HEPDATA.table_renderer.render_keywords(table_data.keywords, "#table_keywords");

        HEPDATA.reset_stats();

        HEPDATA.table_renderer.render_qualifiers(table_data, table_placement);
        HEPDATA.table_renderer.render_headers(table_data, table_placement);
        HEPDATA.table_renderer.render_data(table_data, table_placement);

        HEPDATA.render_associated_files(table_data.associated_files, '#support-files');

        if (table_data["x_count"] > 1) {
          HEPDATA.visualization.heatmap.reset();
          HEPDATA.visualization.heatmap.render(table_data, visualization_placement, {
            width: 300,
            height: 300
          });
        } else {
          HEPDATA.visualization.histogram.render(table_data, visualization_placement, {
            width: 300,
            height: 300,
            "mode": "histogram"
          });
        }

        MathJax.Hub.Queue(["Typeset", MathJax.Hub]);

        HEPDATA.table_renderer.update_reviewer_button(table_data.review);

        $("#hepdata_table_loader").addClass("hidden");
        $("#hepdata_table_content").removeClass("hidden");

      },
      error: function (data, error) {
        console.error('Failed to load table defined by ' + url);
        console.error(error);
      }
    });
  },

  update_reviewer_button: function (review_info) {
    HEPDATA.set_review_status(review_info.review_flag);
  },

  clean_data: function (value, remove_qualifier_uniqueness_attr) {

    if (remove_qualifier_uniqueness_attr) value = value.replace(/-\d+/, "");
    if (value == ".") {
      value = ""
    }
    return value;

  },

  render_keywords: function (keywords, placement) {
    $(placement + " ul").html('');
    var keyword_count = 0;
    for (var keyword_key in keywords) {
      var keyword_values = '';
      var keyword_values_list = '';
      var count = 0;
      for (var value in keywords[keyword_key]) {
        keyword_values += keywords[keyword_key][value];
        count += 1;
        if (count < keywords[keyword_key].length)
          keyword_values += ','
      }

      var li = d3.select(placement + " ul").append('li').attr('id', 'keyword_'+keyword_count)
        .attr('class', 'keyword-item')
        .attr('data-content', keyword_values_list)
        .attr('title', keyword_key)
        .attr({'data-toggle': 'popover', 'data-trigger': 'hover', 'data-placement':"bottom"});

      li.append('span').attr('class', 'keyword-name').text(keyword_key);
      li.append('span').attr('class', 'keyword-value').text(keyword_values.length > 100 ? keyword_values.substring(0, 100) + "..." : keyword_values);

      keyword_count+=1;
    }

    $('.keyword-item').popover();
  },

  render_qualifiers: function (table_data, placement) {
    for (var qualifier_idx in table_data["qualifier_order"]) {
      var qualifier_type = table_data["qualifier_order"][qualifier_idx];

      var qualifier_block = d3.select(placement).append('tr').attr('class', 'qualifiers');

      qualifier_block.append('td').attr('class', 'qualifier_name').attr('colspan', table_data["x_count"]).text(HEPDATA.table_renderer.clean_data(qualifier_type, true));

      for (var qualifier_data_idx in table_data.qualifiers[qualifier_type]) {
        qualifier_block.append('td').attr('class', 'qualifier_value').attr('colspan', table_data.qualifiers[qualifier_type][qualifier_data_idx].colspan).text(HEPDATA.table_renderer.clean_data(table_data.qualifiers[qualifier_type][qualifier_data_idx].value));
      }
    }
  },

  render_headers: function (table_data, placement) {
    var header_section = d3.select(placement).append('tr').attr('class', 'headers');

    for (var header_idx in table_data.headers) {
      header_section.append('td').attr('class', 'x').attr('colspan', table_data.headers[header_idx].colspan).text(table_data.headers[header_idx].name);
    }

  },

  render_data: function (table_data, placement) {

    for (var value_idx in table_data.values) {
      var value_obj = table_data.values[value_idx];

      var tr = d3.select(placement).append("tr").attr("class", "data_values").attr("id", "row-" + value_idx);

      for (var x_idx in value_obj.x) {
        if ('high' in value_obj.x[x_idx]) {
          tr.append('td').text(value_obj.x[x_idx]['low'].toFixed(2) + ' - ' + value_obj.x[x_idx]['high'].toFixed(2));
        } else {
          tr.append("td").text(value_obj.x[x_idx]['value']);
        }
      }

      for (var y_idx in value_obj.y) {
        var value = value_obj.y[y_idx].value;
        var td = tr.append('td');
        if (value != undefined) {

          var div = td.append('div');
          div.append('span').text(value);

          var errors = value_obj.y[y_idx].errors;

          for (var error_idx in errors) {

            var err_class = "error " + ((error_idx < HEPDATA.default_errors_to_show) ? "" : "hidden");

            if ("asymerror" in errors[error_idx]) {

              var plus_error = HEPDATA.visualization.utils.round(errors[error_idx]['asymerror']['plus'], 2);
              var min_error = HEPDATA.visualization.utils.round(errors[error_idx]['asymerror']['minus'], 2);

              var plus_error_num = HEPDATA.dataprocessing.process_error_value(errors[error_idx]['asymerror']['plus'], value);
              var min_error_num = HEPDATA.dataprocessing.process_error_value(errors[error_idx]['asymerror']['minus'], value);

              var error = div.append('div').attr('class', err_class);

              var value_block = error.append('div').attr('class', 'value');
              var asym_block = value_block.append('div').attr('class', 'asym');
              asym_block.append('span').attr('class', 'sup').text((plus_error_num >= 0 ? '+' : '') + plus_error);
              asym_block.append('span').attr('class', 'sub').text((min_error_num > 0 ? '+' : '') + (min_error_num == 0 ? '-' : '') + min_error);
              if (errors[error_idx]["label"] !== undefined)
                value_block.append('div').attr('class', 'label').text(errors[error_idx]["label"] == undefined ? HEPDATA.default_error_label : errors[error_idx]["label"]);

            } else if ("symerror" in errors[error_idx]) {
              if (errors[error_idx]['symerror'] != 0) {

                var sym_error = HEPDATA.visualization.utils.round(errors[error_idx]['symerror'], 2);

                var error = div.append('div').attr('class', err_class + ' sym');

                error.append('div').attr('class', 'value').html('&#177;' + sym_error);

                if (errors[error_idx]["label"] !== undefined)
                  error.append('div').attr('class', 'label').text(errors[error_idx]["label"] == undefined ? HEPDATA.default_error_label : errors[error_idx]["label"]);
              }
            }
          }

          if (errors.length > HEPDATA.default_errors_to_show) {
            div.append('span').text('+ all ' + errors.length + ' more errors').attr('class', 'total_errors');
            div.append('span').attr('class', 'show_all_errors').text('Show all').on('click', function () {

              d3.selectAll('.error.hidden').classed("hidden", false);
              d3.selectAll('.show_all_errors').classed("hidden", true);
              d3.selectAll('.total_errors').classed("hidden", true);
            });
          }
        }
      }
    }
  },

  filter_rows: function (target_rows) {
    $(".data_values").each(function () {
      var row_num = this.id.split("-")[1];
      if (!(row_num in target_rows) && Object.keys(target_rows).length > 0) {
        $(this).addClass("hidden");
      } else {
        $(this).removeClass("hidden");
      }
    });
  }
};

HEPDATA.visualization = {};

HEPDATA.visualization.utils = {

  round: function (value, round) {
    try {
      value = value.toFixed(round)
    } catch (e) {
      console.warn('Unable to convert ' + value + ' to number.');
    }

    return value;
  },

  calculate_x_scale: function (scale_type, min, max, options, data) {

    var x_extent = d3.extent(data, function (d) {
      return d.x;
    });


    if (min == null) {
      //we only get null when the values are not numeric, so in this case we create an ordinal scale
      return d3.scale.ordinal().domain(data.map(function (d) {
        return d.x;
      })).rangePoints([0, options.width - options.margins.left - options.margins.right]);
    } else {
      var scale = scale_type == 'log' && HEPDATA.stats.min_x > 0 ? d3.scale.log() : d3.scale.linear();

      var range = [0, options.width - options.margins.left - options.margins.right];
      if (x_extent[0] == x_extent[1]) {
        var mid_way = (options.width - options.margins.left - options.margins.right) / 2;
        range = [mid_way, mid_way];
      }
      return scale.domain([min, max]).range(range);
    }
  },

  calculate_y_scale: function (scale_type, min, max, options) {
    var scale = scale_type == 'log' && HEPDATA.stats.min_y > 0 ? d3.scale.log() : d3.scale.linear();
    return scale.domain([min, max]).range([options.height - options.margins.top - options.margins.bottom, 0]);
  }
};

HEPDATA.visualization.pie = {

  options: {
    radius: 50,
    animation_duration: 100,
    margins: {"left": 40, "right": 30, "top": 10, "bottom": 30},
    colors: d3.scale.ordinal().domain(['passed', 'attention', 'todo']).range(["#1FA67E", "#f39c12", "#e74c3c"]),
    height: 100,
    width: 250
  },

  render: function (data) {

    var svg = d3.select('#submission-' + data.recid)
      .append('svg')
      .attr('width', HEPDATA.visualization.pie.options.width)
      .attr('height', HEPDATA.visualization.pie.options.height)
      .append('g')
      .attr('transform', 'translate(' + (HEPDATA.visualization.pie.options.width / 2.5) + ',' + (HEPDATA.visualization.pie.options.height / 2) + ')');

    var arc = d3.svg.arc()
      .outerRadius(HEPDATA.visualization.pie.options.radius);

    var pie = d3.layout.pie()
      .value(function (d) {
        return d.count;
      })
      .sort(null);

    var path = svg.selectAll('path')
      .data(pie(data.stats))
      .enter()
      .append('path')
      .attr('d', arc)
      .attr('fill', function (d, i) {
        return HEPDATA.visualization.pie.options.colors(data.stats[i].name);
      });


    svg.selectAll('text.name').data(data.stats).enter().append("text")
      .attr('x', (HEPDATA.visualization.pie.options.radius + 10))
      .attr('y', function (d, i) {
        return (i * 20) - HEPDATA.visualization.pie.options.radius / 3;
      }).style("fill", function (d, i) {
      return HEPDATA.visualization.pie.options.colors(data.stats[i].name);
    }).text(
      function (d, i) {
        return data.stats[i].name;
      }
    ).style("font-size", "0.8em");

    svg.selectAll('text.count').data(data.stats).enter().append("text")
      .attr('x', (HEPDATA.visualization.pie.options.radius + 70))
      .attr('y', function (d, i) {
        return (i * 20) - HEPDATA.visualization.pie.options.radius / 3;
      }).style("fill", function (d, i) {
      return HEPDATA.visualization.pie.options.colors(data.stats[i].name);
    }).text(
      function (d, i) {
        return data.stats[i].count;
      }
    ).style({"font-size": "0.8em", "font-weight": "bolder"});

  }
};

HEPDATA.visualization.heatmap = {

  zoom: undefined,
  brush: undefined,
  x_axis: undefined,
  y_axis: undefined,
  x_scale: undefined,
  y_scale: undefined,
  // points to which independent variable to use when plotting the x and y axes
  x_index: '',
  y_index: '',
  grid_dimension: 10,
  selected: {},
  data: undefined,
  placement: undefined,
  options: {
    brushable: false,
    zoomable: false,
    animation_duration: 100,
    margins: {"left": 60, "right": 30, "top": 10, "bottom": 30},
    // todo: improve the scale used here.
    colors: d3.scale.threshold().domain([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]).range(["#ffffe5", "#ffffe5", "#fff7bc", "#fee391", "#fec44f", "#fe9929", "#ec7014", "#cc4c02", "#993404", "#662506"]),
    height: 400,
    width: 400,
    y_scale: 'linear'
  },

  reset: function () {
    HEPDATA.visualization.heatmap.x_index = '';
  },


  render: function (data, placement, options) {
    $(placement).html('');

    HEPDATA.visualization.heatmap.options = $.extend(HEPDATA.visualization.heatmap.options, options);

    HEPDATA.visualization.heatmap.data = data;

    if (HEPDATA.visualization.heatmap.x_index == '') {
      HEPDATA.visualization.heatmap.x_index = data.headers[1].name;
      HEPDATA.visualization.heatmap.y_index = data.headers[0].name;
    }

    HEPDATA.visualization.heatmap.placement = placement;

    var processed_dict = HEPDATA.dataprocessing.process_data_values(data);
    HEPDATA.visualization.heatmap.render_axis_selector(data, "#legend");

    // in this plot, the x and y axes are defined by two x values in the data. The y 'axis' defines the value
    // and therefore color at the area defined by x, y, and a beam bin size, e.g. 30 GeV.
    HEPDATA.visualization.heatmap.x_scale = HEPDATA.visualization.heatmap.calculate_x_scale(processed_dict['processed']);
    HEPDATA.visualization.heatmap.y_scale = HEPDATA.visualization.heatmap.calculate_y_scale(processed_dict['processed']);

    HEPDATA.visualization.heatmap.x_axis = d3.svg.axis().scale(HEPDATA.visualization.heatmap.x_scale).orient("bottom").tickPadding(2);
    HEPDATA.visualization.heatmap.y_axis = d3.svg.axis().scale(HEPDATA.visualization.heatmap.y_scale).orient("left").tickPadding(2);

    var svg = d3.select(placement).append("svg").attr("width", HEPDATA.visualization.heatmap.options.width).attr("height", HEPDATA.visualization.heatmap.options.height)
      .append("g")
      .attr("transform", "translate(" + HEPDATA.visualization.heatmap.options.margins.left + "," + HEPDATA.visualization.heatmap.options.margins.top + ")");

    var d3tip = d3.tip()
      .attr('class', 'd3-tip')
      .offset([-10, 0])
      .html(function (d) {
        return "<strong>" + d.x + " </strong><br/>" + d.y + "<br/>" + d.value + "</span>";
      });

    svg.append('rect')
      .attr('width', HEPDATA.visualization.heatmap.options.width)
      .attr('height', HEPDATA.visualization.heatmap.options.height)
      .attr('fill', 'rgba(1,1,1,0)');

    svg.append("g").attr("class", "x axis")
      .attr("transform", "translate(0," + (HEPDATA.visualization.heatmap.options.height - HEPDATA.visualization.heatmap.options.margins.bottom - HEPDATA.visualization.heatmap.options.margins.top) + ")")
      .call(HEPDATA.visualization.heatmap.x_axis);
    svg.append("text")
      .attr("class", "axis_text")
      .attr("text-anchor", "middle")
      .attr("x", HEPDATA.visualization.heatmap.options.width / 2)
      .attr("y", HEPDATA.visualization.heatmap.options.height - 10)
      .text(HEPDATA.visualization.heatmap.x_index);


    svg.append("g").attr("class", "y axis").call(HEPDATA.visualization.heatmap.y_axis).attr("transform", "translate(-4,0)");
    svg.append("text")
      .attr("class", "axis_text")
      .attr("text-anchor", "middle")
      .attr("x", -HEPDATA.visualization.heatmap.options.height / 3)
      .attr("y", 0)
      .attr("dy", "-3.5em")
      .attr("transform", "rotate(-90)")
      .text(HEPDATA.visualization.heatmap.y_index);


    var node_data = svg.selectAll("g.hm_node").data(processed_dict["processed"]).enter();

    // we need to scale the data to between 0 and 1 so that the color scale works across different ranges.

    var scale = d3.scale.linear().domain([HEPDATA.stats.min_value, HEPDATA.stats.max_value]).range([0, 1]);


    var node = node_data.append("g").attr("class", "hm_node").append("rect")
      .attr("x", function (d) {
        return HEPDATA.visualization.heatmap.x_scale(d.x)
      })
      .attr("y", function (d) {
        return HEPDATA.visualization.heatmap.y_scale(d.y) - 5;
      })
      .attr("width", function (d) {
        return 5;
      })
      .attr("height", function (d) {
        return 5;
      })
      .style("fill", function (d) {
        return HEPDATA.visualization.heatmap.options.colors(scale(d.value));
      });

    node.on('mouseover', d3tip.show)
      .on('mouseout', d3tip.hide);

    svg.call(d3tip);

    if (HEPDATA.visualization.heatmap.options.brushable) {
      HEPDATA.visualization.heatmap.brush = d3.svg.brush()
        .x(HEPDATA.visualization.heatmap.x_scale)
        .y(HEPDATA.visualization.heatmap.y_scale)
        .on("brushstart", function () {
          HEPDATA.visualization.heatmap.selected = {};
        })
        .on("brush", HEPDATA.visualization.heatmap.brushed)
        .on("brushend", function () {

          HEPDATA.table_renderer.filter_rows(HEPDATA.visualization.heatmap.selected);
        });

      svg.append("g")
        .attr("class", "brush")
        .call(HEPDATA.visualization.heatmap.brush);
    }
  },

  render_brushable_option: function (parent_node, options, function_call) {

    var label = parent_node.append("label").text("Brushing Enabled? ").attr("style", "padding-right:10px");

    var checkbox = parent_node.append("input")
      .attr("type", "checkbox")
      .attr("onClick", function_call);
    if (options.brushable) {
      checkbox.attr("checked", "checked")
    }

    parent_node.append("hr");
  },

  render_axis_selector: function (data, placement) {
    $(placement).html('');
    var options = d3.select(placement).append("div");

    HEPDATA.visualization.heatmap.render_brushable_option(options, HEPDATA.visualization.heatmap.options, "HEPDATA.visualization.heatmap.toggle_brushing(this)");


    options.append("label").text("X Axis").attr("style", "padding-right:10px");
    var selector = options.append("select").attr("class", "hm_axis").attr("id", "hm_xaxis").attr("onchange", "HEPDATA.visualization.heatmap.switch_axis()");

    options.append("br");
    for (var i = 0; i < 2; i++) {
      var option = selector.append("option").text(data.headers[i].name);
      if (data.headers[i].name == HEPDATA.visualization.heatmap.x_index) option.attr("selected", "selected")
    }

    options.append("label").text("Y Axis").attr("style", "padding-right:10px");
    var selector2 = options.append("select").attr("class", "hm_axis").attr("id", "hm_yaxis").attr("onchange", "HEPDATA.visualization.heatmap.switch_axis()");

    for (var i = 0; i < 2; i++) {
      var option = selector2.append("option").text(data.headers[i].name);
      if (data.headers[i].name == HEPDATA.visualization.heatmap.y_index) option.attr("selected", "selected")
    }
  },

  toggle_brushing: function (caller) {
    HEPDATA.visualization.heatmap.options.brushable = d3.select(caller).property("checked");
    HEPDATA.visualization.heatmap.render_axis_selector(HEPDATA.visualization.heatmap.data, "#legend");
    HEPDATA.visualization.heatmap.render(HEPDATA.visualization.heatmap.data, HEPDATA.visualization.heatmap.placement, {});
  },


  switch_axis: function () {
    var tmp_y = HEPDATA.visualization.heatmap.y_index;
    HEPDATA.visualization.heatmap.y_index = HEPDATA.visualization.heatmap.x_index;
    HEPDATA.visualization.heatmap.x_index = tmp_y;

    HEPDATA.visualization.heatmap.render_axis_selector(HEPDATA.visualization.heatmap.data, "#legend");
    HEPDATA.visualization.heatmap.render(HEPDATA.visualization.heatmap.data, HEPDATA.visualization.heatmap.placement, {});
  },

  brushed: function () {
    var extent = HEPDATA.visualization.heatmap.brush.extent();
    HEPDATA.visualization.heatmap.selected = {};
    d3.selectAll("g.hm_node").select("rect").style("stroke", function (d) {

      var x = d.x;
      var y = d.y;

      d.selected = (x >= (extent[0][0]) && x <= (extent[1][0])
      && (y >= extent[0][1]) && (y <= extent[1][1]));

      if (d.selected) {
        HEPDATA.visualization.heatmap.selected[d.row] = d;
      }
      return d.selected ? "#F15D2F" : "none";
    });
  },

  calculate_x_scale: function (data) {
    var x_extent = d3.extent(data, function (d) {
      return d.x;
    });

    return d3.scale.linear().domain(x_extent).range([0, HEPDATA.visualization.heatmap.options.width - HEPDATA.visualization.heatmap.options.margins.left - HEPDATA.visualization.heatmap.options.margins.right]);
  },

  calculate_y_scale: function (data) {
    var y_extent = d3.extent(data, function (d) {
      return d.y;
    });
    return d3.scale.linear().domain(y_extent).range([HEPDATA.visualization.heatmap.options.height - HEPDATA.visualization.heatmap.options.margins.top - HEPDATA.visualization.heatmap.options.margins.bottom, 0]);
  }
};


HEPDATA.visualization.histogram = {

  brush: undefined,
  x_axis: undefined,
  y_axis: undefined,
  x_scale: undefined,
  y_scale: undefined,
  data: undefined,
  histogram_added: false,
  selected: {},
  x_index: '',
  placement: undefined,
  modes: {"scatter": "SCATTER_ONLY", "hist": "HISTOGRAM"},
  options: {
    brushable: true,
    legend_groups: true,
    fill_bars: false,
    draw_summed_error: true,
    animation_duration: 100,
    error_line_width: 0.3,
    margins: {"left": 40, "right": 30, "top": 10, "bottom": 30},
    colors: d3.scale.ordinal().range(["#2C3E50", "#8E44AD", "#27AE60", "#3498DB", "#D35400", "#7F8C8D"]),
    height: 400,
    width: 400,
    mode: "histogram",
    dashed: ["GGM 700 200 1.5"],
    y_scale: 'linear', // can be lin (linear) or log
    x_scale: 'linear' // can be lin (linear) or log
  },

  render: function (data, placement, options) {
    $(placement).html('');

    HEPDATA.visualization.histogram.data = data;
    HEPDATA.visualization.histogram.placement = placement;
    HEPDATA.visualization.histogram.histogram_added = false;

    HEPDATA.visualization.histogram.options = $.extend(HEPDATA.visualization.histogram.options, options);

    var processed_dict = HEPDATA.dataprocessing.process_data_values(data);


    if ((data.headers[0] == undefined || data.headers[0].name == '') && data.values.length == 0) {
      d3.select(placement).append("div").attr("class", "alert alert-warning").text("Unable to render a plot since there is no data to render.");
      d3.select("#legend").html('');
      return
    }

    HEPDATA.visualization.histogram.x_index = data.headers[0].name;

    HEPDATA.visualization.histogram.x_scale = HEPDATA.visualization.utils.calculate_x_scale(HEPDATA.visualization.histogram.options.x_scale, HEPDATA.stats.min_x, HEPDATA.stats.max_x, HEPDATA.visualization.histogram.options, processed_dict["processed"]);
    HEPDATA.visualization.histogram.y_scale = HEPDATA.visualization.utils.calculate_y_scale(HEPDATA.visualization.histogram.options.y_scale, HEPDATA.stats.min_y, HEPDATA.stats.max_y, HEPDATA.visualization.histogram.options);

    HEPDATA.visualization.histogram.x_axis = d3.svg.axis().scale(HEPDATA.visualization.histogram.x_scale).orient("bottom").tickPadding(2);
    HEPDATA.visualization.histogram.y_axis = d3.svg.axis().scale(HEPDATA.visualization.histogram.y_scale).orient("left").tickPadding(2);

    var svg = d3.select(placement).append("svg").attr("width", HEPDATA.visualization.histogram.options.width).attr("height", HEPDATA.visualization.histogram.options.height).attr("preserveAspectRatio", "xMinYMin meet")
      //class to make it responsive
      .classed("svg-content-responsive", true).append("g")
      .attr("transform", "translate(" + HEPDATA.visualization.histogram.options.margins.left + "," + HEPDATA.visualization.histogram.options.margins.top + ")").append("g").attr("class", "plot");

    // we look through the values and create a dictionary mapping a variable to an array of data sorted by the x value.
    // this can then be used to create the lines.
    var _aggregated_values = {};

    for (var value_idx in processed_dict["processed"]) {
      var value_obj = processed_dict["processed"][value_idx];

      if (!(value_obj.name in _aggregated_values )) {
        _aggregated_values[value_obj.name] = {
          "name": value_obj.name,
          "values": [],
          "x_error": "x_min" in value_obj,
          "y_errors": !value_obj.errors[0].hide
        };
      }


      if (_aggregated_values[value_obj.name]["y_errors"]) {
        _aggregated_values[value_obj.name]["values"].push(value_obj);
      } else if (HEPDATA.visualization.histogram.options.mode != HEPDATA.visualization.histogram.modes.scatter && value_obj.x_min) {
        _aggregated_values[value_obj.name]["values"].push({
          x: value_obj.x_min,
          y: value_obj.y,
          errors: value_obj.errors
        });
        _aggregated_values[value_obj.name]["values"].push({
          x: value_obj.x_max,
          y: value_obj.y,
          errors: value_obj.errors
        });
      } else {
        _aggregated_values[value_obj.name]["values"].push(value_obj);
      }
    }

    var line = d3.svg.line()
      .interpolate("linear")
      .x(function (d) {
        return HEPDATA.visualization.histogram.x_scale(d.x);
      })
      .y(function (d) {
        return HEPDATA.visualization.histogram.y_scale(d.y);
      });


    var keys = Object.keys(_aggregated_values);
    for (var i = keys.length - 1; i >= 0; i--) {

      var value = keys[i];

      if (_aggregated_values[value]["y_errors"] || value_obj.x_min == undefined) {
        HEPDATA.visualization.histogram.create_scatter_plot(svg, _aggregated_values[value].values, _aggregated_values[value]["x_error"], _aggregated_values[value]["y_errors"], "histogram", value);
      } else {
        var node = svg.selectAll("g.hist").append('g')
          .data([_aggregated_values[value]]);
        // depending on if there are errors or not, we should change the rendering. Values with errors should be shown as dots with errors bars
        var path = node.enter().append("path")
          .attr("class", function (d) {
            return "hist " + HEPDATA.dataprocessing.cleanup_string(d.name)
          })
          .attr("d", function (d, i) {
            if (HEPDATA.visualization.histogram.options.fill_bars) {
              d.values.unshift({
                x: HEPDATA.stats.min_x,
                y: HEPDATA.stats.min_y
              });
            }
            d.values.push({
              x: HEPDATA.stats.max_x,
              y: HEPDATA.stats.min_y
            });
            var line_path = d.values;
            return line(line_path) + (HEPDATA.visualization.histogram.options.fill_bars ? "z" : "");
          })
          .attr("stroke", function (d) {
            return HEPDATA.visualization.histogram.options.colors(d.name);
          })
          .attr("stroke-dasharray", function (d) {
            if (HEPDATA.visualization.histogram.options.dashed.indexOf(d.name) != -1) {
              return HEPDATA.visualization.histogram.options.width * .009 + ", " + HEPDATA.visualization.histogram.options.width * .015;
            }
          })
          .attr("stroke-width", HEPDATA.visualization.histogram.options.width * .01)
          .attr("fill", function (d) {
            return HEPDATA.visualization.histogram.options.fill_bars ? HEPDATA.visualization.histogram.options.colors(d.name) : "none";
          })
          .attr('opacity', HEPDATA.visualization.histogram.options.fill_bars ? 0.7 : 1)
          .attr("stroke-linecap", "round");

        HEPDATA.visualization.histogram.histogram_added = true;
      }
    }

    var find = '\\$';
    var find_spaces = '\\s+';
    var re_matheq = new RegExp(find, 'g');
    var re_mathspace = new RegExp(find_spaces, 'g');

    HEPDATA.visualization.histogram.x_index = HEPDATA.visualization.histogram.x_index.replace(re_matheq, '');
    HEPDATA.visualization.histogram.x_index = HEPDATA.visualization.histogram.x_index.replace(re_mathspace, '\\;');
    HEPDATA.visualization.histogram.x_index = "$" + HEPDATA.visualization.histogram.x_index + "$";

    svg.append("g").attr("class", "x axis")
      .attr("transform", "translate(0," + (HEPDATA.visualization.histogram.options.height - HEPDATA.visualization.histogram.options.margins.bottom - HEPDATA.visualization.histogram.options.margins.top) + ")")
      .call(HEPDATA.visualization.histogram.x_axis);
    svg.append("foreignObject")
      .attr("class", "axis_text")
      .attr("text-anchor", "end")
      .attr("width", HEPDATA.visualization.histogram.options.width).attr("height", 25)
      .attr("x", HEPDATA.visualization.histogram.options.width / 3)
      .attr("y", HEPDATA.visualization.histogram.options.height - 10)
      .text(HEPDATA.visualization.histogram.x_index);

    svg.append("g").attr("class", "y axis").call(HEPDATA.visualization.histogram.y_axis).attr("transform", "translate(-4,0)");


    HEPDATA.legends.draw_error_legend("#legend", HEPDATA.visualization.histogram.options.draw_summed_error ? processed_dict["quad_error"] : processed_dict["errors"], HEPDATA.visualization.histogram.options);

    if (HEPDATA.visualization.histogram.options.brushable) {
      HEPDATA.visualization.histogram.brush = d3.svg.brush()
        .x(HEPDATA.visualization.histogram.x_scale)
        .y(HEPDATA.visualization.histogram.y_scale)
        .on("brushstart", function () {
          HEPDATA.visualization.histogram.selected = {};
        })
        .on("brush", HEPDATA.visualization.histogram.brushed)
        .on("brushend", function () {
          HEPDATA.table_renderer.filter_rows(HEPDATA.visualization.histogram.selected);
        });

      svg.append("g")
        .attr("class", "brush")
        .call(HEPDATA.visualization.histogram.brush);
    }
  },

  render_option: function (text, type, option, parent_node, function_call) {
    var div = parent_node.append("div").attr("style", "display: inline-block;padding:3px");
    div.append("label").text(text).attr("style", "padding:3px");
    var checkbox = div.append("input")
      .attr("type", "checkbox")
      .attr("onClick", function_call);

    if (type == 'bool') {
      if (HEPDATA.visualization.histogram.options[option]) {
        checkbox.attr("checked", "checked")
      }
    } else if (type == 'scale')
      if (HEPDATA.visualization.histogram.options[option] == "log") {
        checkbox.attr("checked", "checked")
      }
  },


  toggle_scale_option: function (option, caller) {
    HEPDATA.visualization.histogram.options[option] = d3.select(caller).property("checked") ? "log" : "linear";
    HEPDATA.visualization.histogram.render(HEPDATA.visualization.histogram.data, HEPDATA.visualization.histogram.placement, {});
  },

  toggle_bool_option: function (option, caller) {
    HEPDATA.visualization.histogram.options[option] = d3.select(caller).property("checked");
    HEPDATA.visualization.histogram.render(HEPDATA.visualization.histogram.data, HEPDATA.visualization.histogram.placement, {});
  },


  brushed: function () {
    var extent = HEPDATA.visualization.histogram.brush.extent();
    HEPDATA.visualization.histogram.selected = {}

    d3.selectAll("g.node").select("circle").style("fill", function (d) {
      var x = d.x;
      var y = d.y;

      if (isNaN(d.x)) x = HEPDATA.visualization.histogram.x_scale(x);

      d.selected = (x >= (extent[0][0]) && x <= (extent[1][0])
      && (y >= extent[0][1]) && (y <= extent[1][1]));

      if (d.selected) HEPDATA.visualization.histogram.selected[d.row] = d;

      return d.selected ? "#F15D2F" : HEPDATA.visualization.histogram.options.colors(d.name);
    });
  },

  create_scatter_plot: function (svg, values, has_x_error, has_y_error, type, id) {
    var dot_groups = svg.selectAll("g.node " + HEPDATA.dataprocessing.cleanup_string(id)).append('g').attr("class", "node " + HEPDATA.dataprocessing.cleanup_string(id))
      .data(values);

    var dotGroup = dot_groups.enter().append("g").attr("class", function (d) {
      return "node " + HEPDATA.dataprocessing.cleanup_string(d.name);
    }).attr('transform', function (d) {
      return "translate(" + (HEPDATA.visualization[type].x_scale(d.x)) + "," + HEPDATA.visualization[type].y_scale(d.y) + ")";
    });

    // draw x errors if they should be drawn :)
    if (has_x_error) {
      dot_groups.selectAll('rect.x_err').data(function (d) {
        return [d];
      }).enter()
        .append("rect")
        .attr("x", function (d) {
          return HEPDATA.visualization[type].x_scale(d.x_min) - HEPDATA.visualization[type].x_scale(d.x);
        })
        .attr("y", 0)
        .attr("width", function (d) {
          return HEPDATA.visualization[type].x_scale((d.x_max)) - HEPDATA.visualization[type].x_scale((d.x_min));
        })
        .attr("height", 1)
        .style("stroke", "#2C3E50")
        .attr("class", function (d, i) {
          var variable = HEPDATA.dataprocessing.cleanup_string(d.name);
          return "x_err ebar-" + variable;
        })
    }

    if (has_y_error) {

      if (HEPDATA.visualization[type].options.draw_summed_error) {
        dot_groups.append("line")
          .attr("x1", 0)
          .attr("y1", function (d) {
            return HEPDATA.visualization[type].y_scale(d.y + d.quad_error.err_minus) - HEPDATA.visualization[type].y_scale(d.y);
          })
          .attr("x2", 0)
          .attr("y2", function (d) {
            return HEPDATA.visualization[type].y_scale(d.y + d.quad_error.err_plus) - HEPDATA.visualization[type].y_scale(d.y);
          })
          .attr("stroke-width", 2)
          .style("stroke", "#2C3E50")
          .attr("class", function (d, i) {
            var label = d.quad_error.label == undefined ? HEPDATA.default_error_label : d.quad_error.label;
            label = HEPDATA.dataprocessing.cleanup_string(label);
            var variable = HEPDATA.dataprocessing.cleanup_string(d.name);
            return "y_err line error-" + label + " " + variable + "-error-" + label + " ebar-" + variable;
          });
      }
      else {

        dot_groups.selectAll('rect.y_err').data(function (d) {
          return d.errors;
        }).enter()
          .append("line")
          .attr("x1", 0)
          .attr("y1", function (d) {
            return HEPDATA.visualization[type].y_scale(d.y + d.err_minus) - HEPDATA.visualization[type].y_scale(d.y);
          })
          .attr("x2", 0)
          .attr("y2", function (d) {
            return HEPDATA.visualization[type].y_scale(d.y + d.err_plus) - HEPDATA.visualization[type].y_scale(d.y);
          })

          .attr("stroke-width", 2)
          .style("stroke", "#2C3E50")
          .attr("class", function (d, i) {
            var label = d.label == undefined ? HEPDATA.default_error_label : d.label;
            label = HEPDATA.dataprocessing.cleanup_string(label);
            var variable = HEPDATA.dataprocessing.cleanup_string(d.name);
            return "y_err line error-" + label + " " + variable + "-error-" + label + " ebar-" + variable;
          });
      }
    }

    dotGroup.append("circle")
      .attr("r", 3)
      .attr("class", "dot")
      .style("fill", function (d) {
        return HEPDATA.visualization[type].options.colors(d.name);
      })
  }
};

HEPDATA.dataprocessing = {
  /**
   * The data values come in a format relevant for tables, but not so good for use with D3.
   * We need to flatten things out in to objects representing each X,Y pair for display
   * @param data_values
   */
  process_data_values: function (data) {
    var processed_values = [];
    var toignore = [];
    var all_errors = [];
    var all_quad_errors = [];
    var groups = {};

    var group_types = {};
    for (var qualifier_key in data.qualifiers) {
      var qualifiers_record = data.qualifiers[qualifier_key];
      for (var qualifier_value_idx in qualifiers_record) {
        var qualifier_record = qualifiers_record[qualifier_value_idx];
        if (!(qualifier_record.group in groups)) {
          groups[qualifier_record.group] = [];
        }
        groups[qualifier_record.group].push(qualifier_record);

        if (!(qualifier_record.type in group_types)) {
          group_types[qualifier_record.type] = {
            "set": new Set(),
            "values": []
          };
        }

        group_types[qualifier_record.type]["set"].add(qualifier_record.value)
        group_types[qualifier_record.type]["values"].push(qualifier_record.value)
      }
    }

    var best_key = undefined;
    var headers = data.headers;

    var expanded_headers = [];
    for (var header_obj in headers) {
      for (var i = 0; i < headers[header_obj].colspan; i++) {
        expanded_headers.push(headers[header_obj])
      }
    }

    for (var key in group_types) {
      if (group_types[key]["set"].size == (expanded_headers.length - 1)) {
        best_key = key;
      }
    }


    for (var data_record in data.values) {
      var record = data.values[data_record];
      for (var y_idx in record.y) {
        if (record.y[y_idx].value != null) {
          var processed_value = {};
          if (expanded_headers[+y_idx + 1]) {
            var data_header_value = expanded_headers[+y_idx + 1].name;

            if (group_types[best_key]) {
              data_header_value += "::" + best_key + ":" + group_types[best_key]["values"][y_idx] + "::" + y_idx;
            }

            if (record.x.length > 1) {

              var x1_idx = 0, x2_idx = 1;
              for (var idx = 0; idx < HEPDATA.visualization.heatmap.data.headers.length; idx++) {
                if (HEPDATA.visualization.heatmap.data.headers[idx].name == HEPDATA.visualization.heatmap.x_index) {
                  x1_idx = idx;
                }
                if (HEPDATA.visualization.heatmap.data.headers[idx].name == HEPDATA.visualization.heatmap.y_index) {
                  y1_idx = idx;
                }
              }

              processed_value = {

                "x": record.x[x1_idx],
                "y": record.x[y1_idx],
                "value": record.y[y_idx].value,
                "name": data_header_value,
                "row": data_record
              };


              if (isNaN(processed_value.value)) continue;

              if (processed_value.value < HEPDATA.stats.min_value) HEPDATA.stats.min_value = processed_value.value;
              if (processed_value.value > HEPDATA.stats.max_value) HEPDATA.stats.max_value = processed_value.value;

            } else {
              processed_value = {
                "x": record.x[0],
                "y": record.y[y_idx].value,
                "name": data_header_value,
                "row": data_record
              };
              if (processed_value.y == '-') continue;
            }

            processed_value = HEPDATA.dataprocessing.processed_key(processed_value, 'x');
            processed_value = HEPDATA.dataprocessing.processed_key(processed_value, 'y');

            var errors = [];

            var summed_uncertainties = {"up": 0, "down": 0};

            for (var error_idx in record.y[y_idx].errors) {

              var errors_obj = $.extend(record.y[y_idx].errors[error_idx], {});
              errors_obj.x = processed_value.x;
              errors_obj.y = record.y[y_idx].value;
              errors_obj.group = record.y[y_idx].group;
              errors_obj.name = data_header_value;

              if ("asymerror" in errors_obj) {
                var up_err = HEPDATA.dataprocessing.process_error_value(errors_obj['asymerror']['plus'], errors_obj.y);
                var down_err = HEPDATA.dataprocessing.process_error_value(errors_obj['asymerror']['minus'], errors_obj.y);
                errors_obj.err_plus = Math.max(down_err, up_err, 0);
                errors_obj.err_minus = Math.min(down_err, up_err, 0);

              } else if ("symerror" in errors_obj) {
                //we have a symerror
                var value = HEPDATA.dataprocessing.process_error_value(errors_obj['symerror'], errors_obj.y);
                errors_obj.err_plus = value;
                errors_obj.err_minus = value == 0 ? 0 : -value;
              }

              if (errors_obj.y + errors_obj.err_plus > HEPDATA.stats.max_y) HEPDATA.stats.max_y = errors_obj.err_plus + errors_obj.y;
              if (errors_obj.y + errors_obj.err_minus < HEPDATA.stats.min_y) HEPDATA.stats.min_y = errors_obj.err_minus + errors_obj.y;

              summed_uncertainties["up"] += Math.pow(errors_obj.err_plus, 2);
              summed_uncertainties["down"] += Math.pow(errors_obj.err_minus, 2);

              errors.push(errors_obj);
              all_errors.push(errors_obj);
            }


            processed_value["quad_error"] = {
              x: processed_value.x,
              y: record.y[y_idx].value,
              'err_plus': Math.sqrt(summed_uncertainties["up"]),
              'err_minus': -Math.sqrt(summed_uncertainties["down"]),
              'label': 'Summed',
              'name': data_header_value
            };

            if (summed_uncertainties["up"] == 0 && summed_uncertainties["down"] == 0) {
              processed_value["quad_error"]["label"] = "hidden";
            }

            all_quad_errors.push(processed_value["quad_error"]);

            processed_value["errors"] = errors;
            processed_value["group"] = record.y[y_idx].group;
            processed_values.push(processed_value);
          }
        } else {
          toignore.push(record.x);
        }
      }
    }


    return {
      "processed": processed_values,
      "ignore": toignore,
      "errors": all_errors,
      "quad_error": all_quad_errors,
      "groups": groups
    };
  },

  process_error_value: function (error_value, value) {
    //we need to check if percentage values etc.
    if (isNaN(error_value) && error_value.indexOf('%') != -1) {
      //we have a percentage, deal with this
      error_value = parseFloat(error_value.replace("%", ""));
      error_value = (value / 100) * error_value;

      return error_value;
    } else {
      return parseFloat(error_value);
    }
  },

  /**
   * Processes X ranges specified as 0.1 - 0.4 in to the start range, end range, and mid value.
   * @param processed_value_obj
   * @param key - e.g. x or y to be processed
   */
  processed_key: function (processed_value_obj, key) {
    var val = processed_value_obj[key];
    if (val != undefined) {
      if (!isNaN(parseFloat(val["high"])) && !isNaN(parseFloat(val["low"]))) {
        var value = val["value"];
        try {
          value = parseFloat(val["value"])
        } catch (e) {
          console.error(e)
        }

        var high = parseFloat(val["high"]);
        var low = parseFloat(val["low"]);

        high = Math.max(low, high);
        low = Math.min(low, high);

        if (!isNaN(value)) {
          processed_value_obj[key + '_max'] = high;
          processed_value_obj[key + '_min'] = low;
          processed_value_obj[key] = value;
        } else {
          processed_value_obj[key + '_min'] = low;
          processed_value_obj[key + '_max'] = high;
          processed_value_obj[key] = high - ((high - low) / 2);
        }

        if (processed_value_obj[key + '_max'] > HEPDATA.stats['max_' + key])  HEPDATA.stats['max_' + key] = processed_value_obj[key + '_max'];
        if (processed_value_obj[key + '_min'] < HEPDATA.stats['min_' + key])  HEPDATA.stats['min_' + key] = processed_value_obj[key + '_min'];
      } else if (!isNaN(parseFloat(val["value"]))) {
        processed_value_obj[key] = +val["value"];

        if (processed_value_obj[key] > HEPDATA.stats['max_' + key])  HEPDATA.stats['max_' + key] = processed_value_obj[key];
        if (processed_value_obj[key] < HEPDATA.stats['min_' + key])  HEPDATA.stats['min_' + key] = processed_value_obj[key];

      } else {
        if (key == 'x') {
          processed_value_obj[key] = val["value"];
          HEPDATA.stats['max_' + key] = null;
          HEPDATA.stats['min_' + key] = null;
        }
      }
    }
    return processed_value_obj;
  },


  /**
   * Removes non-alpha characters from the start of a string string, and non-alphanum characters
   * from the rest of the string.
   * @param string
   */
  cleanup_string: function (string) {
    if (string) {
      //remove numbers from the beginning of the string..
      if (isNaN(string)) {
        string = HEPDATA.dataprocessing.convert_number_to_string(string);
      }
      string = string.replace(/^[[\-|\+]*[0-9\*\s]+/gi, "");
      return string.replace(/[^a-zA-Z0-9]+/gi, "");
    } else {
      return '';
    }
  },

  /**
   * In the event where a string is just a number, we need to get an alpha representation
   * @param string
   */
  convert_number_to_string: function (string) {
    var converted = '';
    for (var a in string) {
      if (isNaN(string[a])) {
        converted += string[a]
      } else {
        converted += String.fromCharCode(97 + parseInt(string[a]))
      }
    }
    return converted;
  }
};

HEPDATA.legends = {

  draw_error_legend: function (legend_placement, all_variables, options) {
    d3.select(legend_placement).html('');

    var rendering_options = d3.select(legend_placement).append("div").attr("class", "options");
    HEPDATA.visualization.histogram.render_option("Sum errors", 'bool', "draw_summed_error", rendering_options, "HEPDATA.visualization.histogram.toggle_bool_option('draw_summed_error', this)");

    if (HEPDATA.visualization.histogram.histogram_added) {
      HEPDATA.visualization.histogram.render_option("Fill bars", 'bool', "fill_bars", rendering_options, "HEPDATA.visualization.histogram.toggle_bool_option('fill_bars', this)");
    }

    if (HEPDATA.stats.min_x > 0) HEPDATA.visualization.histogram.render_option("Log Scale (X)", 'scale', "x_scale", rendering_options, "HEPDATA.visualization.histogram.toggle_scale_option('x_scale', this)");
    if (HEPDATA.stats.min_y > 0) HEPDATA.visualization.histogram.render_option("Log Scale (Y)", 'scale', "y_scale", rendering_options, "HEPDATA.visualization.histogram.toggle_scale_option('y_scale', this)");

    rendering_options.append("hr");
    d3.select(legend_placement).append("div").attr("class", "legend-info").text("Deselect variables or hide different error bars by clicking on them.");

    var table = d3.select(legend_placement).append("table").attr("class", "legend-table").style("table-layout", "fixed");

    var thead = table.append("thead").append("tr");
    thead.append("td").attr('style', 'padding-top:10px').text("Variables");

    var tbody = table.append("tbody");

    var variables = {};
    all_variables.map(function (d) {

      d.label = d.label == "" ? HEPDATA.default_error_label : d.label;
      if (!(d.name in variables)) {
        variables[d.name] = [];
      }

      if (!d.hide) {
        if (variables[d.name].indexOf(d.label) == -1) {
          variables[d.name].push(d.label);
        }
      }
    });

    for (var variable_name in variables) {

      var cleaned_var_name = HEPDATA.dataprocessing.cleanup_string(variable_name);
      var variable_parts = variable_name.split("::");

      var tr = tbody.append("tr");
      var td = tr.append("td").text(variable_parts[0]).attr("id", cleaned_var_name)
        .attr("class", "error-legend-item variable-name").style("color", options.colors(variable_name)).style("border-bottom", options.colors(variable_name));

      td.append('div').attr('class', 'error-qualifier-info').text(variable_parts[1]);

      var errors = variables[variable_name];

      for (var error in errors) {
        var error_value = errors[error] == undefined ? HEPDATA.default_error_label : errors[error];
        if (error_value != "hidden") {
          var tr = tbody.append("tr");
          tr.append("td").text(error_value + " error").attr("class", function () {
              return "variable-error error-legend-item error-" + cleaned_var_name;
            })
            .attr("id", cleaned_var_name + "-error-" + HEPDATA.dataprocessing.cleanup_string(error_value)
            )
        }
      }
      tbody.append("div").attr("class", "clearfix");
    }

    $(".error-legend-item").bind('click', function () {
      var item_id = this.id;
      // we need to have logic in place for the variable display and error display
      d3.selectAll("." + this.id).transition().duration(100).style("opacity", function () {
        var this_opacity = d3.select(this).style("opacity");
        var overall_opacity = this_opacity == 1 ? 0.4 : 1;

        d3.select("#" + item_id).transition().duration(100).style("opacity", overall_opacity);
        if (overall_opacity < 0.5) {
          d3.selectAll(".ebar-" + item_id).transition().duration(100).style("opacity", 0);
          d3.selectAll(".error-" + item_id).transition().duration(100).style("opacity", 0.4);
        } else {
          d3.selectAll(".ebar-" + item_id).transition().duration(100).style("opacity", 1);
          d3.selectAll(".error-" + item_id).transition().duration(100).style("opacity", 1);
        }
        return overall_opacity < 0.5 ? 0 : 1;

      });
    });

    MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
  }


};

HEPDATA.render_loader = function (placement, events, options) {

  if (HEPDATA.interval == undefined) {
    clearInterval(HEPDATA.interval);
  }
  d3.select(placement).html('');
  var svg = d3.select(placement).append("svg").attr("width", options.width).attr("height", options.height).append("g");

  svg.append("rect").attr("width", options.width).attr("height", options.height).attr('fill', 'rgba(1,1,1,0)');


  var scaleX = d3.scale.linear()
    .domain([-100, 100])
    .range([0, options.width]);

  var scaleY = d3.scale.linear()
    .domain([-100, 100])
    .range([options.height, 0]);


  var line = d3.svg.line()
    .interpolate("basis")
    .x(function (d) {
      return scaleX(d.x);
    })
    .y(function (d) {
      return scaleY(d.y);
    });

  //draw detector rings
  svg.append("circle").attr("cx", options.width / 2).attr("cy", options.width / 2).attr("r", options.width * .02).attr("fill", "none").attr("stroke", "#955BA5").attr("stroke-width", options.width * .01).attr("stroke-linecap", "round");
  svg.append("circle").attr("cx", options.width / 2).attr("cy", options.width / 2).attr("r", options.width * .2).attr("fill", "none").attr("stroke", "#955BA5").attr("stroke-width", options.width * .03).attr("stroke-linecap", "round");


  var path = svg.selectAll("path")
    .data(events)
    .enter().append("path")
    .attr("d", function (d, i) {
      d['delay'] = i * 300;
      var line_path = [{x: 0, y: 0}, {x: d.x / 6, y: d.y + 2}, d];
      return line(line_path)
    })
    .attr("stroke", function (d) {
      return d.color;
    })
    .attr("stroke-width", options.width * .015)
    .attr("fill", "none")
    .attr("stroke-linecap", "round");

  function start_outgoing_animation(events) {

    path
      .attr("stroke-dasharray", function () {
        return d3.select(this).node().getTotalLength() + " " + d3.select(this).node().getTotalLength()
      })
      .attr("stroke-dashoffset", function () {
        return d3.select(this).node().getTotalLength();
      })
      .transition()
      .duration(1500)
      .delay(function (d) {
        return d.delay;
      })
      .ease("linear")
      .attr("stroke-dashoffset", 0);

    return path;
  }

  function start_incoming_animation(path) {
    path
      .transition()
      .delay(function (d) {
        return d.delay + 4000;
      })
      .duration(2000)
      .ease("linear")
      .attr("stroke-dashoffset", function () {
        return d3.select(this).node().getTotalLength();
      });
  }

  var path = start_outgoing_animation(events);
  start_incoming_animation(path);


  HEPDATA.interval = setInterval(function () {
    start_outgoing_animation(events);
    start_incoming_animation(path);
  }, 9000);
};

HEPDATA.render_about_animation = function (placement) {

  window.requestAnimFrame = function () {
    return (
      window.requestAnimationFrame ||
      window.webkitRequestAnimationFrame ||
      window.mozRequestAnimationFrame ||
      window.oRequestAnimationFrame ||
      window.msRequestAnimationFrame ||
      function (/* function */ callback) {
        window.setTimeout(callback, 2000 / 60);
      }
    );
  }();

  window.cancelAnimFrame = function () {
    return (
      window.cancelAnimationFrame ||
      window.webkitCancelAnimationFrame ||
      window.mozCancelAnimationFrame ||
      window.oCancelAnimationFrame ||
      window.msCancelAnimationFrame ||
      function (id) {
        window.clearTimeout(id);
      }
    );
  }();

  function SVGEl(el) {
    this.el = el;
    this.image = this.el.previousElementSibling;
    this.current_frame = 0;
    this.total_frames = 150;
    this.path = [];
    this.length = [];
    this.handle = 0;
    this.init();
  }

  SVGEl.prototype.init = function () {
    var self = this;
    [].slice.call(this.el.querySelectorAll('path')).forEach(function (path, i) {
      self.path[i] = path;
      var l = self.path[i].getTotalLength();
      self.length[i] = l;
      self.path[i].style.strokeDasharray = l + ' ' + l;
      self.path[i].style.strokeDashoffset = l;
    });
  };

  SVGEl.prototype.render = function () {
    if (this.rendered) return;
    this.rendered = true;
    this.draw();
  };

  SVGEl.prototype.draw = function () {
    var self = this,
      progress = this.current_frame / this.total_frames;
    if (progress > 1) {
      window.cancelAnimFrame(this.handle);
    } else {
      this.current_frame++;
      for (var j = 0, len = this.path.length; j < len; j++) {
        this.path[j].style.strokeDashoffset = Math.floor(this.length[j] * (1 - progress));
      }
      this.handle = window.requestAnimFrame(function () {
        self.draw();
      });
    }
  };


  var svgs = Array.prototype.slice.call(document.querySelectorAll(placement)),
    svgArr = [],
    resizeTimeout;


  // the svgs already shown...
  svgs.forEach(function (el, i) {
    var svg = new SVGEl(el);
    svgArr[i] = svg;
    setTimeout(function (el) {
      return function () {

        svg.render();

      };
    }(el), 250);
  });

};


