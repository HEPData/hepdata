/**
 * Created by eamonnmaguire on 04/10/2016.
 */

var submissions_vis = (function () {


  var status_colors = d3.scale.ordinal().domain(["finished", "todo", "in progress"]).range(["#1abc9c", "#e74c3c", "#f39c12"]);
  var general_colors = d3.scale.ordinal().range(["#2980b9"]);

  var date_format = "%d %b %Y";

  var formatDate = d3.time.format(date_format);

  var parseDate = function (d) {
    return new Date(d.substring(0, 4),
      d.substring(5, 7) - 1,
      d.substring(8));
  };

  var sortByDateAscending = function (a, b) {

    if (typeof a === 'string') {
      var a = d3.time.format(date_format).parse(a);
      var b = d3.time.format(date_format).parse(b);
      return b - a;
    } else {
      return b.last_updated - a.last_updated;
    }

  };

  function getTopValues(map, count) {

    var tupleArray = [];
    for (var key in map) tupleArray.push([key, map[key]]);
    tupleArray.sort(function (a, b) {
      return b[1] - a[1];
    });

    var result = [];
    for (var i = 0; i < Math.min(count, tupleArray.length); i++) {
      result.push({key: tupleArray[i][0], value: tupleArray[i][1]});
    }
    return result;
  }


  var calculate_window_width = function () {
    return $(window).width();
  };

  var calculate_vis_width = function (window_width, normal_width_ratio) {
    if (window_width <= 900) {
      return window_width * .63;
    } else {
      return window_width * normal_width_ratio;
    }
  };

  var process_data = function (data) {
    data.forEach(function (d, i) {
      console.log(d.collaboration);
      d.index = i;

      d.last_updated = parseDate(d.last_updated);
      d.creation_date = parseDate(d.creation_date);
    });
  };

  function getHighestValues(source_group) {
    return {
      all: function () {
        var values = getTopValues(source_group, 20);
        return values;
      }
    };
  }


  function getTops(source_group) {
    return {
      all: function () {

        return source_group.top(10);
      }
    };
  }

  function getContributors(source_group) {
    return {
      all: function () {
        return source_group.top(10);
      }
    };
  }

  function remove_empty_bins(source_group) {
    return {
      all: function () {
        return source_group.all().filter(function (d) {
          return d.value != 0;
        });
      }
    };
  }

  function reduceAdd(p, v) {
    v.participants.forEach(function (val, idx) {
      p[val] = (p[val] || 0) + 1; //increment counts
    });
    return p;
  }

  function reduceRemove(p, v) {
    v.participants.forEach(function (val, idx) {
      p[val] = (p[val] || 0) - 1; //decrement counts
    });
    return p;

  }

  function reduceInitial() {
    return {};
  }

  return {
    render: function (url, options) {
      d3.json(url, function (result) {

        MathJax.Hub.Config({
          tex2jax: {inlineMath: [['$', '$'], ['\\(', '\\)']]}
        });

        var submission_data = result;

        process_data(submission_data);

        var submissions = crossfilter(submission_data),

          submissions_by_date = submissions.dimension(function (d) {
            return d.last_updated;
          }),

          data = submissions.dimension(function (d) {
            return d.data_count;
          }),

          participants = submissions.dimension(function (d) {
            return d.participants;
          }),

          collaboration = submissions.dimension(function (d) {
            return d.collaboration == '' ? 'No collaboration' : d.collaboration;
          }),

          status = submissions.dimension(function (d) {
            return d.status;
          }),

          version = submissions.dimension(function (d) {
            return d.version;
          }),

          participantsGroup = participants.groupAll().reduce(reduceAdd, reduceRemove, reduceInitial).value(),

          submissions_by_date_count_group = submissions_by_date.group(),
          cumulative_count = submissions_by_date.group().reduceSum(),
          collaboration_count_group = collaboration.group(),
          status_count_group = status.group(),
          data_count_group = data.group(),
          version_count_group = version.group();


        participantsGroup.all = function () {
          var newObject = [];
          for (var key in this) {
            if (this.hasOwnProperty(key) && key != "all") {
              newObject.push({
                key: key,
                value: this[key]
              });
            }
          }
          return newObject;
        };

        var minDate = new Date(submissions_by_date.bottom(1)[0].last_updated);
        var maxDate = new Date(submissions_by_date.top(1)[0].last_updated);

        minDate.setDate(minDate.getDate() - 1);
        maxDate.setDate(maxDate.getDate() + 1);

        var window_width = calculate_window_width();

        var submission_chart = dc.barChart("#submission_vis")
          .height(200)
          .width(calculate_vis_width(window_width, 0.95))
          .x(d3.time.scale().domain([minDate, maxDate]))
          .dimension(submissions_by_date, 'Submissions')
          .group(submissions_by_date_count_group)
          .colors(general_colors);

        // submission_chart.on("preRedraw", function (chart) {
        //   var group = chart.group();
        //   var new_group = {
        //     all: function () {
        //       return group.all().filter(function (d) {
        //         return d.value != 0;
        //       })
        //     }
        //   };
        //   chart.group(new_group);
        // });
        //
        // submission_chart.elasticX(true);

        var collaboration_chart = dc.rowChart("#collaboration_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .height(250)
          .dimension(collaboration, 'collaborations')
          .group(getTops(collaboration_count_group))
          .colors(general_colors);


        var participant_chart = dc.rowChart("#participants_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .height(575)
          .dimension(participants, 'participants')
          .group(getHighestValues(participantsGroup))
          .colors(general_colors);

        var status_chart = dc.pieChart("#status_vis")

          .width(calculate_vis_width(window_width, 0.12))
          .dimension(status, 'status')
          .group(status_count_group)
          .innerRadius(40)
          .colors(status_colors);

        var version_chart = dc.pieChart("#version_vis")

          .width(calculate_vis_width(window_width, 0.12))
          .dimension(version, 'versions')
          .group(version_count_group)
          .innerRadius(40)
          .colors(general_colors);

        var data_count = dc.barChart("#data_count_vis")
          .height(250)
          .width(calculate_vis_width(window_width, 0.3))
          .x(d3.scale.linear().domain([0, 45]))
          .dimension(data, 'data')
          .group(data_count_group)
          .colors(general_colors);

        var detailTable = dc.dataTable('#data_table');
        detailTable.dimension(submissions_by_date)
          .group(function (d) {
            return '<i class="fa fa-calendar"></i> ' + formatDate(d.last_updated);
          })

          .columns([
            function () {
              return ""
            },
            function (d) {
              return d.inspire_id;
            },

            function (d) {
              var link_id = d.inspire_id ? 'ins' + d.inspire_id : d.recid;
              return '<div class="label version">Version ' + d.version + '</div>' +
                '<a href="/record/' + link_id + '" target="_blank">' + d.title + '</a>';
            },

            function (d) {
              return '<span class="badge badge-success">' + d.data_count + '</span>';
            },

            function (d) {
              return '<span class="label ' + d.status + '">' + d.status + '</span>';
            },
            function (d) {
              if (d.collaboration) {
                return '<a href="/search/?q=&collaboration=' +
                  d.collaboration + '" target="_blank">' + '<span class="label ' + d.collaboration + '">' + d.collaboration + '</span>' + '</a>';
              }
            }
          ]).sortBy(function (d) {
          return d.last_updated;
        })
          .order(sortByDateAscending);

        detailTable.on("redraw", function (chart) {
          alert("filtered");
          MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
        });


        dc.renderAll();
      });
    }
  }


})();
