import $ from "jquery"
import HEPDATA from './hepdata_common.js'

$(document).ready(function(){

  $('.question-option').click(function () {
      if ($(this).hasClass('table-show')) {
          $(".question-option, .question-view").animate({
              right: "+=300"
          }, 400);
          $(this).html('<span class="fa fa-chevron-right"></span>').removeClass('table-show').addClass('table-hide');
      }
      else {
          $(".question-option, .question-view").animate({
              right: "-=300"
          }, 400);
          $(this).html('<span class="fa fa-question"></span>').removeClass('table-hide').addClass('table-show');

      }
  });

  $("#send").click(function () {

      var message = $("#question").val();

      var DATA = {
          'question': message
      };
      $.ajax({
          type: "POST",
          dataType: "json",
          url: "/record/question/" + HEPDATA.current_record_id,
          data: DATA,
          cache: false,
          success: function (data) {
              $("#question-container").html('<p>Question sent...</p>');
          }
      });

  });

});
