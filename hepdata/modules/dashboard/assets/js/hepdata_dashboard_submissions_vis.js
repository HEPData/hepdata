/**
 * Created by eamonnmaguire on 04/10/2016.
 */
import $ from 'jquery'
import crossfilter from 'crossfilter2'
import d3 from 'd3'
import dc from 'dc'
import HEPDATA from './hepdata_common.js'
import './hepdata_dashboard_user_filter.js'
import './hepdata_loaders.js'


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
      d.index = i;

      d.last_updated = parseDate(d.last_updated);
      d.creation_date = parseDate(d.creation_date);
    });
  };

  function getTops(source_group, count) {
    if (!count) {
      count = 10;
    }
    return {
      all: function () {
        return source_group.top(count);
      }
    };
  }

  function resetCharts(charts) {
    console.log("Aaargh");
    charts.forEach(function (c) {
      c.filterAll();
    });
    charts.forEach(function (c) {
      c.redraw();
    });
  }

  return {
    display_loader: function() {
      HEPDATA.render_loader(
        '#submissions-dashboard-loader',
        [
          {x: 26, y: 30, color: "#955BA5"},
          {x: -60, y: 55, color: "#FFFFFF"},
          {x: 37, y: -10, color: "#955BA5"},
          {x: -60, y: 10, color: "#955BA5"},
          {x: -27, y: -30, color: "#955BA5"},
          {x: 60, y: -55, color: "#FFFFFF"}
        ],
        {"width": 200, "height": 200}
      );
    },

    render: function (url, options) {
      d3.json(url, function (result) {

        var submission_data = result;
        var submission_dashboard_container = $('#submissions-dashboard-contents');

        if (submission_data.length == 0) {
          submission_dashboard_container.html(
            '<div align="center" class="alert alert-info">You are not yet the coordinator for any submissions.</div>'
          );
          $('#submissions-dashboard-loader').hide()
          submission_dashboard_container.show();
          return;
        }

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
          }, true),

          collaboration = submissions.dimension(function (d) {
            return d.collaboration == '' ? 'No collaboration' : d.collaboration;
          }),

          coordinator = submissions.dimension(function (d) {
            return d.coordinator_group ? d.coordinator_group : d.coordinator;
          }),

          status = submissions.dimension(function (d) {
            return d.status;
          }),

          version = submissions.dimension(function (d) {
            return d.version;
          }),

          participantsGroup = participants.group(),
          submissions_by_date_count_group = submissions_by_date.group(),
          cumulative_count = submissions_by_date.group().reduceSum(),
          collaboration_count_group = collaboration.group(),
          coordinator_count_group = coordinator.group(),
          status_count_group = status.group(),
          data_count_group = data.group(),
          version_count_group = version.group();

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

        var collaboration_chart = dc.rowChart("#collaboration_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .height(250)
          .dimension(collaboration, 'collaborations')
          .group(getTops(collaboration_count_group))
          .colors(general_colors);

        var coordinator_chart = dc.rowChart("#coordinator_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .height(250)
          .dimension(coordinator, 'coordinators')
          .group(getTops(coordinator_count_group))
          .colors(general_colors);

        var participant_chart = dc.rowChart("#participants_vis")
          .width(calculate_vis_width(window_width, 0.3))
          .height(575)
          .dimension(participants, 'participants')
          .group(getTops(participantsGroup, 20))
          .colors(general_colors);

        var status_chart = dc.pieChart("#status_vis")

          .width(calculate_vis_width(window_width, 0.11))
          .dimension(status, 'status')
          .group(status_count_group)
          .innerRadius(40)
          .colors(status_colors);

        var version_chart = dc.pieChart("#version_vis")

          .width(calculate_vis_width(window_width, 0.11))
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
              var link_id = d.inspire_id && d.status == 'finished' ? 'ins' + d.inspire_id : d.recid;
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
            },
            function (d) {
              if (d.participants) {
                // Add in a space after each comma (end of participant).
                return '<span>' + String(d.participants).replace(',', ', ') + '</span>';
              }
            }
          ]).sortBy(function (d) {
          return d.last_updated;
        })
          .order(sortByDateAscending);

        $('#submissions-dashboard-loader').hide()
        submission_dashboard_container.show();
        dc.renderAll();

        $('#submissions-vis-reset').click(function() {
          resetCharts([
            submission_chart,
            data_count,
            participant_chart,
            collaboration_chart,
            coordinator_chart,
            status_chart,
            version_chart,
            detailTable
          ]);
        });
      });
    }
  }

})();

$(document).ready(function () {
    HEPDATA.initialise_user_filter();
    submissions_vis.display_loader();
    submissions_vis.render('/dashboard/submissions/list', {});
});
