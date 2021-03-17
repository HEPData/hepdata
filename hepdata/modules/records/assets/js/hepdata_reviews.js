/**
 * Created by eamonnmaguire on 16/03/2016.
 */
import $ from 'jquery'
import d3 from 'd3'
import HEPDATA from './hepdata_common.js'

HEPDATA.set_review_status = function (status, set_all_tables) {
  var data = {
    "publication_recid": HEPDATA.current_record_id,
    "status": status,
    "version": HEPDATA.current_table_version
  }
  if (set_all_tables) {
    data["all_tables"] = true
  } else {
    data["data_recid"] = HEPDATA.current_table_id
  }

  $.ajax({
      type: "POST",
      url: "/record/data/review/status/",
      dataType: "json",
      data: data,
      cache: false,
      success: function (data) {
        var status = data.status;
        if (status) {
          HEPDATA.update_review_statuses(status)
        } else {
          if (data.success) {
            $("#approve-all-container .col-md-12 div p").html('All tables passed. Reloading in 1s...');
            setTimeout(function () { window.location.reload(true); }, 1000);
          } else {
            var closeButtonHtml = '<button type="button" class="btn btn-info" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">Close</span></button>';
            $("#approve-all-container .col-md-12").append('<p>Failed. Please try again later.</p>' + closeButtonHtml);
          }
        }
      }
    }
  );
};

HEPDATA.update_review_statuses = function(status) {
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
  HEPDATA.toggleApproveAllButton();
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
        d3.selectAll("#conversation_message_count").html(message_count);
      }
      $("#conversation_message_count").html(message_count);
    }
  });
};

HEPDATA.render_review_message = function (placement, message) {
  var date_time = message.post_time.split(" ");
  var message_container = d3.select(placement).append('div').attr('class', 'container-fluid');
  var message_item = message_container.append('div').attr('class', 'message-item row-fluid');
  var message_info = message_item.append('div').attr('class', 'message-info col-md-12');
  message_info.append('p').attr('class', 'message-time').html(date_time[0] + ' at ' + date_time[1] + ' UTC');
  var message_div = message_item.append('div').attr('class', 'message-content col-md-12');
  message_div.append('p').attr('class', 'reviewer').text(message.user);
  message_div.append('p').text(message.message);
  message_item.append('div').attr('class', 'clearfix');
};

HEPDATA.load_review_messages = function (placement, record_id, table_id) {
  d3.select(placement).html('');
  $.ajax({
      type: "GET",
      url: "/record/data/review/message/" + table_id + "/" + HEPDATA.current_table_version,
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

HEPDATA.toggleApproveAllButton = function() {
  var approveAllButton = $('#approve-all-btn');
  if (approveAllButton) {
    if($('.review-status.todo[id*="-status"],.review-status.attention[id*="-status"]').length) {
      approveAllButton.show();
    } else {
      approveAllButton.hide();
    }
  }
}

$(document).ready(function() {
  $('.review-option').click(function () {
      if ($(this).hasClass('table-show')) {
          $(".review-option, .reviews-view").animate({
              right: "+=300"
          }, 400);
          $(this).html('<span class="fa fa-chevron-right"></span>').removeClass('table-show').addClass('table-hide');
      }
      else {
          $(".review-option, .reviews-view").animate({
              right: "-=300"
          }, 400);
          $(this).html('<span class="fa fa-comments"></span>').removeClass('table-hide').addClass('table-show');

      }
  });

  $(".input_box").on('change keyup paste', function(e) {
    if(this.value) {
      $("#send .btn-primary").prop('disabled', false);
    } else {
      $("#send .btn-primary").prop('disabled', true);
    }
  });

  $("#send").click(function () {

      var message = $(".input_box").val();

      var DATA = {
          'message': message,
          'version': HEPDATA.current_table_version
      };
      $.ajax({
          type: "POST",
          dataType: "json",
          url: "/record/data/review/message/" + HEPDATA.current_record_id + "/" + HEPDATA.current_table_id,
          data: DATA,
          cache: false,
          success: function (data) {


              if ($("#review_messages").text() == 'No messages yet...') {
                  $("#review_messages").text('');
              }

              var message = data.message;
              var date_time = data.post_time.split(" ");
              var html = '<div class="message-item">' +
                      '<div class="message-info">' +
                      '<p class="message-time">' + date_time[0] + ' at ' + date_time[1] + ' UTC</p>' +
                      '</div>' +
                      '<div class="message-content">' +
                      '<p class="reviewer">Sender:  ' + data.user + '</p>' + message + '</div>' +
                      '</div>';

              $("#table-" + HEPDATA.current_table_id + "-messages").removeClass("hidden");
              $(html).prependTo("#review_messages").slideDown("slow");
              $(".input_box").val('');
              $("#send .btn-primary").prop('disabled', true);
          }
      });
      return false;
  });

  $("#review-status span").click(function () {
      HEPDATA.set_review_status(this.id.split("-")[0])
  });

});
